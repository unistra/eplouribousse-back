from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site

from epl.apps.project.models import ActionLog, Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name",)


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = (
        "action_time",
        "actor",
        "action_message",
        "content_object",
    )
    search_fields = (
        "action_message",
        "actor",
    )
    list_filter = ("action_time",)


admin.site.unregister(Site)
admin.site.unregister(Group)
