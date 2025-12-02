from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from epl.apps.tenant.models import Consortium


@admin.register(Consortium)
class ConsortiumAdmin(TenantAdminMixin, admin.ModelAdmin):
    pass
