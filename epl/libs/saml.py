import importlib
from pathlib import Path

from django.conf import settings
from django.http import HttpRequest
from saml2.config import SPConfig


def load_config(settings_file: Path) -> dict:
    module_name = settings_file.stem
    spec = importlib.util.spec_from_file_location(module_name, settings_file)
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)

    return config_module.SAML_CONFIG


def saml_config_loader(request: HttpRequest) -> SPConfig:
    """
    We have the SAML_CONFIG stored in a file for each tenant, so we need to load it dynamically
    """
    conf = SPConfig()
    tenant_domain = ""
    if tenant := getattr(request, "tenant"):
        tenant_domain: str = tenant.get_primary_domain().domain

    settings_file = settings.SITE_ROOT / f"epl/settings/saml2/{tenant_domain}.py"
    if settings_file.exists():
        config = load_config(settings_file)
    else:
        config = settings.SAML_CONFIG

    conf.load(config)

    return conf
