import json
from pathlib import Path, PosixPath

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from jsonschema import validate
from jsonschema.exceptions import ValidationError as SchemaValidationError
from rest_framework import serializers


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
                validate(value, schema)
            except SchemaValidationError as e:
                raise serializers.ValidationError(f"Invalid JSON schema: {str(e)}")
        return value
