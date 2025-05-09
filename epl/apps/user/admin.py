from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from epl.apps.user.models import User, UserRole


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    pass


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "project", "role", "assigned_at", "assigned_by")
    list_filter = ("role", "project")
    search_fields = ("user__email", "user__username", "project__name")
    date_hierarchy = "assigned_at"
