import importlib
from os import environ
from pathlib import Path
from typing import Any

from django.conf import settings
from django.http import HttpRequest
from saml2.config import SPConfig


def resolve_references(value: Any, context: dict[str, str]) -> Any:
    # Some values in the SAML_CONFIG might be references to constants in saml2 module
    if isinstance(value, str) and "{{" in value and "}}" in value:
        # Replace {{ reference }} with actual value from context
        for k, v in context.items():
            value = value.replace(f"{{{{ {k} }}}}", v)
    elif isinstance(value, dict):
        return {k: resolve_references(v, context) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_references(item, context) for item in value]
    elif isinstance(value, tuple):
        return tuple(resolve_references(item, context) for item in value)
    return value


def load_config(settings_file: Path, context: dict[str, str]) -> dict:
    module_name = settings_file.stem
    spec = importlib.util.spec_from_file_location(module_name, settings_file)
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)

    config = config_module.SAML_CONFIG
    config = resolve_references(config, context)

    return config


def saml_config_loader(request: HttpRequest) -> SPConfig:
    conf = SPConfig()
    tenant_domain = ""
    if tenant := getattr(request, "tenant"):
        tenant_domain: str = tenant.get_primary_domain().domain

    settings_file = settings.SITE_ROOT / "epl/settings/saml2/saml_config.py"
    if settings_file.exists():
        context = {"SITE_DOMAIN": tenant_domain.rstrip("/"), "ENV": environ.get("ENVIRONMENT")}
        config = load_config(settings_file, context)
    else:
        config = settings.SAML_CONFIG

    conf.load(config)

    return conf
