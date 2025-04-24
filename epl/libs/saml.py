import copy

from django.conf import settings
from django.http import HttpRequest
from saml2.config import SPConfig


def saml_config_loader(request: HttpRequest) -> SPConfig:
    conf = SPConfig()
    schema_name = ""
    if tenant := getattr(request, "tenant"):
        schema_name = tenant.schema_name

    saml_config: dict = getattr(settings, "SAML_CONFIG", {})
    copied_config: dict = copy.deepcopy(saml_config)

    try:
        if hasattr(settings, "SAML_TENANT_CONFIG") and settings.SAML_TENANT_CONFIG.get(schema_name, {}):
            # we have customizations for this tenant
            custom_config = settings.SAML_TENANT_CONFIG[schema_name]
            copied_config.update(custom_config)
    except AttributeError:
        pass

    conf.load(copy.deepcopy(copied_config))

    return conf
