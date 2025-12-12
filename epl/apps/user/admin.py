from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from epl.apps.project.models import UserRole
from epl.apps.user.models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    readonly_fields = ("date_joined", "last_login")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
        ("Settings", {"fields": ("settings",)}),
    )


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "project", "role", "assigned_at", "assigned_by")
    list_filter = ("role", "project")
    search_fields = ("user__email", "user__username", "project__name")
    date_hierarchy = "assigned_at"
