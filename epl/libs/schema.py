import json
from pathlib import Path

from django.conf import settings


def load_json_schema(schema_file):
    schema_path = settings.DJANGO_ROOT / "schemas" / schema_file

    with Path(schema_path).open() as f:
        schema = json.load(f)

    # Adapts the JSON schema to the format expected by extend_schema_field
    # Replaces 'const' with 'enum' for OpenAPI compatibility
    if "oneOf" in schema:
        for item in schema["oneOf"]:
            if "properties" in item and "type" in item["properties"] and "const" in item["properties"]["type"]:
                const_value = item["properties"]["type"]["const"]
                item["properties"]["type"] = {"type": "string", "enum": [const_value]}

    # Adds external docs to reference the original schema
    schema["externalDocs"] = {
        "description": "Complete JSON schema documentation",
        "url": f"/schema/{schema_file}",
    }

    return schema
