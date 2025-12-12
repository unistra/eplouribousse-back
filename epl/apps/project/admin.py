from django.contrib import admin

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
