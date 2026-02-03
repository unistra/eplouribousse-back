from django.apps import AppConfig


class UserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "epl.apps.user"

    def ready(self):
        import epl.apps.user.extensions  # noqa: F401
        import epl.apps.user.signals  # noqa: F401
