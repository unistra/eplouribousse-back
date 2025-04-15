from django.db import models
from django.utils.translation import gettext_lazy as _
from django_tenants.models import DomainMixin, TenantMixin

from epl.models import UUIDPrimaryKeyField


class Consortium(TenantMixin):
    id = UUIDPrimaryKeyField()
    name = models.CharField(_("Tenant name"), max_length=100)
    tenant_settings = models.JSONField(_("Tenant settings"), default=dict)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)

    auto_create_schema = True


class Domain(DomainMixin):
    id = UUIDPrimaryKeyField()
    front_domain = models.CharField(_("Frontend domain"), max_length=253, blank=True)
