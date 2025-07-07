from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import signing
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _
from rest_framework.request import Request

from epl.apps.user.models import User
from epl.services.tenant import get_front_domain


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


def send_password_reset_email(user: User, front_domain: str):
    token = PasswordResetTokenGenerator().make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    email_content = render_to_string(
        "emails/password_reset.txt",
        {
            "front_domain": front_domain,
            "token": token,
            "uid": uid,
        },
    )

    user.email_user(
        subject=f"[eplouribousse] {_('Password Reset')}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        fail_silently=True,
        message=email_content,
    )


def send_invite_to_epl_email(
    email: str,
    request: Request,
    signer: signing.TimestampSigner,
    project_id: str = None,
    library_id: str = None,
    role: str = None,
    assigned_by_id=None,
) -> None:
    invite_token: str = signer.sign_object(
        {
            "email": str(email),
            "project_id": str(project_id) if project_id else None,
            "library_id": str(library_id) if library_id else None,
            "role": str(role) if role else None,
            "assigned_by_id": str(assigned_by_id) if assigned_by_id else None,
        }
    )

    front_domain = get_front_domain(request)
    invitation_link = f"{front_domain}/create-account?t={invite_token}"

    email_content = render_to_string(
        "emails/invite_to_epl.txt",
        {"email_support": settings.EMAIL_SUPPORT, "invitation_link": invitation_link},
    )

    send_mail(
        subject=f"[eplouribousse] {_('Invitation')}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
        message=email_content,
    )


def send_invite_project_admins_to_review_email(
    email: str,
    request: Request,
    project_name: str,
    project_id: str,
) -> None:
    front_domain = get_front_domain(request)
    invitation_link = f"{front_domain}/review-project/{project_id}"  # todo: modify ou retour au dashboard (plus simple)

    email_content = render_to_string(
        "emails/invite_project_admin_to_review.txt",
        {
            "email_support": settings.EMAIL_SUPPORT,
            "invitation_link": invitation_link,
            "project_name": project_name,
        },
    )

    send_mail(
        subject=f"[eplouribousse] {_('Invitation to review project')}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
        message=email_content,
    )
