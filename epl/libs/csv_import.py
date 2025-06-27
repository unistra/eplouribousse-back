from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, field_validator

from epl.validators import IssnValidator


class CollectionModel(BaseModel):
    title: Annotated[str, Field(alias="Titre", max_length=510)]
    code: Annotated[str, Field(alias="PPN", max_length=25)]
    issn: Annotated[str, Field(alias="Issn", max_length=9)] = ""
    call_number: Annotated[str, Field(alias="Cote")] = ""
    hold_statement: Annotated[str, Field(alias="Etat de collection")] = ""
    missing: Annotated[str, Field(alias="Lacunes")] = ""
    created_by_id: UUID
    project_id: UUID
    library_id: UUID

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
        except Exception as err:
            raise ValueError(f"Invalid ISSN: {str(err)}")
        return value


def handle_import(
    csv_reader, library_id: UUID, project_id: UUID, created_by: UUID
) -> tuple[list[CollectionModel], list[tuple[int, Any]]]:
    collections = []
    errors = []
    row_number = 1  # Start counting rows from 2 as the first row is the header

    for row in csv_reader:
        row_number += 1
        try:
            collections.append(
                CollectionModel(**row, created_by_id=created_by, project_id=project_id, library_id=library_id)
            )
        except ValidationError as e:
            errors.append((row_number, str(e)))

    return collections, errors
