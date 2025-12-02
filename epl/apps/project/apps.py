from django.apps import AppConfig


class ProjectConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "epl.apps.project"

    def ready(self):
        """Import signals after the app is ready."""
        import epl.apps.project.signals  # noqa
