from django.conf import settings
from django.utils.translation.trans_null import get_supported_language_variant

from epl.apps.project.models import Project
from epl.apps.user.models import User


def get_user_language(user: User, project: Project):
    """
    Determine the language to be used for the response.

    Priority:
    1. User's preferred language
    2. Project's default language
    3. Fallback to settings.LANGUAGE_CODE
    """
    if user.is_authenticated and user.preferred_language:
        return user.preferred_language

    if project and project.default_language:
        return project.default_language

    try:
        lang = settings.LANGUAGE_CODE
        return get_supported_language_variant(lang)
    except (LookupError, AttributeError):
        return "fr"  # fallback to French
