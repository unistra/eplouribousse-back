from django.db.models.signals import post_save
from django.dispatch import receiver

from .models.project import DEFAULT_EXCLUSION_REASONS, Project


@receiver(post_save, sender=Project)
def initialize_project_settings(sender, instance, **kwargs):
    """
    Initialize default project settings on creation.
    Add default exclusion reasons if not already set.
    """
    if kwargs["created"]:
        instance.settings["exclusion_reasons"] = DEFAULT_EXCLUSION_REASONS.copy()
        instance.save(update_fields=["settings"])
