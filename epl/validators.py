import json
from pathlib import Path, PosixPath

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _
from jsonschema import RefResolver, validate
from jsonschema.exceptions import ValidationError as SchemaValidationError
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

                # tweak to allow internal ref resolving in schema
                # source: https://stackoverflow.com/questions/25145160/json-schema-ref-does-not-work-for-relative-path
                # Delete the $id key from the schema to avoid network calls
                schema_copy = schema.copy()
                if "$id" in schema_copy:
                    del schema_copy["$id"]

                # Create the resolver with the schema directory as the base_uri
                schema_dir = self.schema.parent
                schema_path = f"file:///{schema_dir}/"
                resolver = RefResolver(schema_path, schema_copy)
                validate(value, schema_copy, resolver=resolver)

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
