from django.db import models
from django_tenants.models import DomainMixin, TenantMixin

from epl.models import UUIDPrimaryKeyField


class Consortium(TenantMixin):
    id = UUIDPrimaryKeyField()
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    auto_create_schema = True


class Domain(DomainMixin):
    id = UUIDPrimaryKeyField()
