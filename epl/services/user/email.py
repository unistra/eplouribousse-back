from datetime import datetime

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from rest_framework.request import Request


def send_password_change_email(user: Request.user):
    email_content = render_to_string(
        "emails/password_changed.txt",
        {
            "user": user,
            "year": datetime.now().year,
            "email_support": settings.EMAIL_SUPPORT,
        },
    )

    user.email_user(
        subject=f"[eplouribousse] {_('Password Change')}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        fail_silently=True,
        message=email_content,
    )
