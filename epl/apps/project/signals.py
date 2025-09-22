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
        exclusion_reasons = [
            str(reason) for reason in DEFAULT_EXCLUSION_REASONS
        ]  # traduction is forced at the evaluation of the str function
        instance.settings["exclusion_reasons"] = exclusion_reasons
        instance.settings["alerts"] = {
            "positioning": False,
            "arbitration0": False,
            "arbitration1": False,
            "instructions": False,
            "results": False,
            "transferTracking": False,
            "treatmentTracking": False,
        }
        instance.save(update_fields=["settings"])
