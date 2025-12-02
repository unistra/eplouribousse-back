import json
from pathlib import Path, PosixPath

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaValidationError
from referencing import Registry, Resource
from rest_framework import serializers
from stdnum import issn
from stdnum.exceptions import ValidationError as StdValidationError


class JSONSchemaValidator:
    def __init__(self, schema):
        if not isinstance(schema, PosixPath):
            schema = settings.DJANGO_ROOT / "schemas" / schema
        if not schema.is_file():
            raise ImproperlyConfigured(
                f"JSON schema file {schema} does not exist or is not readable",
            )

        self.schema = schema

    def __call__(self, value):
        with Path(self.schema).open() as f:
            try:
                schema = json.load(f)

                # Load all schemas from the schema directory
                registry = Registry()
                schema_dir = self.schema.parent

                for schema_file in schema_dir.glob("*.json"):
                    with schema_file.open() as f:
                        schema_content = json.load(f)

                    resource = Resource.from_contents(schema_content)
                    registry = registry.with_resource(schema_file.name, resource)  # Add schema to registry

                # Validation with registry
                validator = Draft202012Validator(schema, registry=registry)
                validator.validate(value)

            except SchemaValidationError as e:
                raise serializers.ValidationError(f"Invalid JSON schema: {str(e)}")
        return value


@deconstructible
class IssnValidator:
    """
    Validate that the given ISSN is valid and format uppercase with - separator
    """

    def __call__(self, value: str) -> str:
        issn_to_check = value.replace("-", "").replace(" ", "").upper()
        if len(issn_to_check) != 8:
            raise serializers.ValidationError(_("ISSN must be 8 characters long"))
        try:
            issn.validate(issn_to_check)
        except StdValidationError as e:
            raise serializers.ValidationError(f"Invalid ISSN {str(e)}")
        return f"{issn_to_check[:4]}-{issn_to_check[4:]}"
