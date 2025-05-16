from django.contrib import admin

from epl.apps.project.models import Project  # Ajustez selon votre structure


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at")  # Ajustez selon vos champs
    search_fields = ("name",)
