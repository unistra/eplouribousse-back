from datetime import datetime

from django.conf import settings
from django.core.mail import send_mail
from django.core.signing import TimestampSigner
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response


def send_password_change_email(user: Request.user):
    email_content = render_to_string(
        "emails/password_changed.txt",
        {
            "email_support": settings.EMAIL_SUPPORT,
        },
    )

    user.email_user(
        subject=f"[eplouribousse] {_('Password Change')}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        fail_silently=True,
        message=email_content,
    )


def send_password_reset_email(user, email: str, domain, protocol, port=""):
    signer = TimestampSigner(salt="reset-password")
    token = signer.sign_object({email: email})
    email_content = render_to_string(
        "emails/password_reset.txt",
        {
            "user": user,
            "domain": domain,
            "protocol": protocol,
            "port": port,
            "year": datetime.now().year,
            "token": token,
            "email_support": settings.EMAIL_SUPPORT,
        },
    )

    user.email_user(
        subject=f"[eplouribousse] {_('Password Reset')}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        fail_silently=True,
        message=email_content,
    )


def send_invite_email(email: str) -> Response:
    email_content = render_to_string(
        "emails/invite.txt",
        {
            "email_support": settings.EMAIL_SUPPORT,
        },
    )

    try:
        send_mail(
            subject=f"[eplouribousse] {_('Invitation')}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
            message=email_content,
        )
        return Response(status=status.HTTP_200_OK)
    except Exception:
        return Response({"details": _("Email sending failed")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
