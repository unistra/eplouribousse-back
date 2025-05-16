from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from rest_framework.request import Request


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


def send_password_reset_email(user, reset_link: str):
    email_content = render_to_string(
        "emails/password_reset.txt",
        {
            "reset_link": reset_link,
        },
    )

    user.email_user(
        subject=f"[eplouribousse] {_('Password Reset')}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        fail_silently=True,
        message=email_content,
    )


def send_invite_email(email: str, request: Request, signer: signing.TimestampSigner) -> None:
    invite_token: str = signer.sign_object({"email": str(request.data["email"])})

    invitation_link = f"{request.scheme}://{request.tenant.get_primary_domain().front_domain}{':5173' if request.scheme == 'http' else ''}/create-account?t={invite_token}"
    print(invitation_link)

    email_content = render_to_string(
        "emails/invite.txt",
        {"email_support": settings.EMAIL_SUPPORT, "invitation_link": invitation_link},
    )

    send_mail(
        subject=f"[eplouribousse] {_('Invitation')}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
        message=email_content,
    )
