import json
import uuid
from typing import Annotated, Any, TypedDict
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, field_validator

from epl.validators import IssnValidator


class CollectionModel(BaseModel):
    call_number: Annotated[str, Field(alias="Cote")] = ""
    hold_statement: Annotated[str, Field(alias="Etat de collection")] = ""
    missing: Annotated[str, Field(alias="Lacunes")] = ""
    resource_id: UUID
    created_by_id: UUID
    project_id: UUID
    library_id: UUID

    @field_validator("*", mode="before")
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class ResourceModel(BaseModel):
    id: UUID
    title: Annotated[str, Field(max_length=510, min_length=1)]
    code: Annotated[str, Field(min_length=1, max_length=25)]
    project_id: UUID
    issn: Annotated[str, Field(max_length=9)] = ""
    numbering: Annotated[str, Field(alias="Numerotation")] = ""
    publication_history: Annotated[str, Field(alias="PublieEn")] = ""

    @field_validator("*", mode="before")
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("issn", mode="before")
    @classmethod
    def validate_issn(cls, value: str) -> str:
        if value:
            value = value.strip().upper()
        try:
            value = IssnValidator()(value)
        except Exception:
            raise ValueError("Invalid ISSN")
        return value


class CodesT(TypedDict):
    id: UUID
    count: int


def handle_import(
    csv_reader, library_id: UUID, project_id: UUID, created_by: UUID
) -> tuple[list[CollectionModel], list[ResourceModel], dict[str, CodesT], list[tuple[int, Any]]]:
    collections = []
    resources = []
    errors = []
    row_number = 1  # Start counting rows from 2 as the first row is the header

    codes: dict[str, CodesT] = {}  # To track resource codes

    for row in csv_reader:
        row_number += 1
        ppn = row.pop("PPN").strip()
        titre = row.pop("Titre").strip()
        issn = row.pop("Issn", "").strip()
        numbering = row.pop("PublieEn", "").strip()
        publication_history = row.pop("Publication history", "").strip()

        if not codes.get(ppn):
            try:
                resource = ResourceModel(
                    id=uuid.uuid4(),
                    code=ppn,
                    title=titre,
                    issn=issn,
                    publication_history=publication_history,
                    numbering=numbering,
                    project_id=project_id,
                )
                codes[ppn] = {"id": resource.id, "count": 1}
                resources.append(resource)
            except ValidationError as e:
                errors.append((row_number, json.loads(e.json())))
                continue
        else:
            codes[ppn]["count"] += 1

        try:
            collections.append(
                CollectionModel(
                    **row,
                    resource_id=codes.get(ppn)["id"],
                    created_by_id=created_by,
                    project_id=project_id,
                    library_id=library_id,
                )
            )
        except ValidationError as e:
            errors.append((row_number, json.loads(e.json())))

    return collections, resources, codes, errors
