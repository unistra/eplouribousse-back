from typing import Any

from django.contrib.auth import user_logged_in
from django.db.models import Model
from django.dispatch import receiver

from epl.apps.project.models import ActionLog


@receiver(user_logged_in)
def log_user_login(sender: type[Model], request: Any, user: Any, **kwargs: Any) -> None:
    if request.saml_session:
        message = "User has logged in via SAML"
    else:
        message = "User has logged in"
    ActionLog.log(message=message, actor=user, obj=user, request=request)
