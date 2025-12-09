from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import signing
from django.core.mail import EmailMessage, send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _
from rest_framework.request import Request

from epl.apps.project.models import Project, Resource, Role
from epl.apps.project.models.collection import Arbitration
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
    invitations: list = None,
    assigned_by_id=None,
) -> None:
    invite_token: str = signer.sign_object(
        {
            "email": str(email),
            "project_id": str(project_id) if project_id else None,
            "invitations": invitations or [],
            "assigned_by_id": str(assigned_by_id) if assigned_by_id else None,
        }
    )

    front_domain = get_front_domain(request)
    invitation_link = f"{front_domain}/create-account?t={invite_token}"

    email_content = render_to_string(
        "emails/invite_to_epl.txt",
        {
            "email_support": settings.EMAIL_SUPPORT,
            "invitation_link": invitation_link,
            "inviter": request.user.email,
        },
    )

    send_mail(
        subject=f"eplouribousse | {request.tenant.name} | " + _("creating your account (pending)"),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
        message=email_content,
    )


def send_account_created_email(user: User, request: Request) -> None:
    front_domain = get_front_domain(request)
    tenant_url = f"{front_domain}/"

    email_content = render_to_string(
        "emails/confirm_account_creation.txt",
        {
            "tenant_url": tenant_url,
            "username": user.email,
        },
    )

    subject = f"eplouribousse | {request.tenant.name} | {_('your account creation')}"

    send_mail(
        subject=subject,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
        message=email_content,
    )


def send_invite_project_admins_to_review_email(
    email: str,
    request: Request,
    project_name: str,
    tenant_name: str,
    project_creator_email: str,
) -> None:
    front_domain = get_front_domain(request)

    email_content = render_to_string(
        "emails/invite_project_admins_to_review.txt",
        {
            "email_support": settings.EMAIL_SUPPORT,
            "project_name": project_name,
            "front_domain": front_domain,
            "tenant_name": tenant_name,
            "project_creator_email": project_creator_email,
        },
    )

    send_mail(
        subject=f"eplouribousse | {tenant_name} | "
        + _("Creation of the {project_name} project").format(project_name=project_name),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
        message=email_content,
    )


def send_invite_project_managers_to_launch_email(
    email: str,
    request: Request,
    project: Project,
    tenant_name: str,
    action_user_email: str,
) -> None:
    front_domain = get_front_domain(request)
    project_url = f"{front_domain}/projects/{project.id}"

    email_content = render_to_string(
        "emails/invite_project_managers_to_launch.txt",
        {
            "email_support": settings.EMAIL_SUPPORT,
            "project_name": project.name,
            "front_domain": front_domain,
            "tenant_name": tenant_name,
            "action_user_email": action_user_email,
            "project_url": project_url,
        },
    )

    send_mail(
        subject=f"eplouribousse | {tenant_name} | "
        + _("Availability of the {project_name} project for launch").format(project_name=project.name),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
        message=email_content,
    )


def send_project_launched_email(
    request: Request, project: Project, project_users: list[str], is_starting_now: bool
) -> None:
    front_domain = get_front_domain(request)
    project_url = f"{front_domain}/projects/{project.id}"

    active_date = project.active_after

    email_content = render_to_string(
        "emails/project_launched.txt",
        {
            "project_name": project.name,
            "launcher_name": request.user.email,
            "project_active_date": _("now")
            if is_starting_now
            else f"{active_date.strftime('%Y-%m-%d')} {_('at')} {active_date.strftime('%H:%M')}",
            "project_url": project_url,
            "email_support": settings.EMAIL_SUPPORT,
            "is_starting_now": is_starting_now,
        },
    )

    send_mail(
        subject=f"eplouribousse | {request.tenant.name} | "
        + _("Launch of the {project_name} project").format(project_name=project.name),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=project_users,
        fail_silently=False,
        message=email_content,
    )


def send_arbitration_notification_email(
    email: str, request: Request, resource: Resource, library_code: str, arbitration_type: Arbitration
) -> None:
    front_domain = get_front_domain(request)
    project = resource.project
    tenant = request.tenant
    project_url = f"{front_domain}/projects/{project.id}"

    # Choisir le template en fonction du type d'arbitrage
    template_name = f"emails/notify_arbitration_type{arbitration_type.value}.txt"

    email_content = render_to_string(
        template_name,
        {
            "resource_title": resource.title,
            "project_url": project_url,
        },
    )

    subject = f"eplouribousse | {tenant.name} | {project.name} | {library_code} | {resource.code} | {_('arbitration')} {arbitration_type.value}"

    send_mail(
        subject=subject,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
        message=email_content,
    )


def send_collection_positioned_email(
    email: str,
    request: Request,
    resource: Resource,
    positioned_collection,
) -> None:
    """
    Notifies instructors that have not yet positionned their collections for a resource,
    that another collection for the same resource has been positioned.
    This message is sent only if at least one collection has not been positioned yet.
    """
    front_domain = get_front_domain(request)
    project = resource.project
    tenant = request.tenant
    project_url = f"{front_domain}/projects/{project.id}"

    email_content = render_to_string(
        "emails/notify_positioning.txt",
        {
            "library_code": positioned_collection.library.code,
            "project_url": project_url,
        },
    )

    subject = f"eplouribousse | {tenant.name} | {project.name} | {positioned_collection.library.code} | {resource.code} | {_('positioning')}"

    send_mail(
        subject=subject,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
        message=email_content,
    )


def send_instruction_turn_email(
    email: str,
    request: Request,
    resource: Resource,
    library_code: str,
) -> None:
    """
    Notifies an instructor that it's their turn to instruct their collection.
    """
    front_domain = get_front_domain(request)
    project = resource.project
    tenant = request.tenant
    project_url = f"{front_domain}/projects/{project.id}"

    subject = f"eplouribousse | {tenant.name} | {project.name} | {library_code} | {resource.code} | {_('instruction')}"

    email_content = render_to_string(
        "emails/notify_instruction_turn.txt",
        {
            "resource_title": resource.title,
            "project_url": project_url,
        },
    )

    send_mail(
        subject=str(subject),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
        message=email_content,
    )


def send_control_notification_email(
    email: str,
    request,
    resource,
    cycle: str,  # "reliés" ou "non-reliés"
):
    front_domain = get_front_domain(request)
    project = resource.project
    tenant = request.tenant
    project_url = f"{front_domain}/projects/{project.id}"
    subject = f"eplouribousse | {tenant.name} | {project.name} | {resource.code} | {_('control')}"

    email_content = render_to_string(
        "emails/notify_control.txt",
        {
            "cycle": cycle,
            "resource_title": resource.title,
            "project_url": project_url,
        },
    )

    send_mail(
        subject=subject,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
        message=email_content,
    )


def send_anomaly_notification_email(
    email: str,
    request: Request,
    resource: Resource,
    reporter_user: User,
) -> None:
    front_domain = get_front_domain(request)
    project = resource.project
    tenant = request.tenant
    modal_url = f"{front_domain}/projects/{project.id}/?resource={resource.id}"

    # Get the request user role label in the project and verify authorization
    reporter_role_display = None
    if reporter_user.is_controller(project):
        reporter_role_display = Role.CONTROLLER.label
    elif reporter_user.is_instructor(project):
        reporter_role_display = Role.INSTRUCTOR.label

    subject = f"eplouribousse | {tenant.name} | {project.name} | {resource.code} | {_('anomaly')}"

    email_content = render_to_string(
        "emails/notify_anomalies.txt",
        {
            "resource_title": resource.title,
            "reporter_role": reporter_role_display,
            "reporter_identifier": str(reporter_user),
            "reporter_email": reporter_user.email,
            "modal_url": modal_url,
        },
    )

    send_mail(
        subject=subject,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
        message=email_content,
    )


def send_anomaly_resolved_notification_email(
    to_emails: list[str],
    cc_emails: list[str],
    request: Request,
    resource: Resource,
    library_code: str,
    admin_user: User,
) -> None:
    """
    Sends an email notification when anomalies are resolved and instruction turn is assigned.

    Args:
        to_emails: List of primary recipients (instructors with turn + project admins)
        cc_emails: List of CC recipients (other instructors concerned)
        request: HTTP request object
        resource: The resource for which anomalies were resolved
        library_code: Code of the library that got the instruction turn
        admin_user: The administrator who resolved the anomaly
    """

    front_domain = get_front_domain(request)
    project = resource.project
    tenant = request.tenant
    modal_url = f"{front_domain}/projects/{project.id}/?resource={resource.id}"

    subject = f"eplouribousse | {tenant.name} | {project.name} | {resource.code} | {_('anomaly resolved')}"

    email_content = render_to_string(
        "emails/notify_anomaly_resolved.txt",
        {
            "library_code": library_code,
            "resource_title": resource.title,
            "admin_user_display_name": str(admin_user),
            "admin_email": admin_user.email,
            "modal_url": modal_url,
        },
    )

    # Create EmailMessage with TO and CC recipients
    email_message = EmailMessage(
        subject=subject,
        body=email_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to_emails,
        cc=cc_emails,
    )

    email_message.send(fail_silently=False)


def send_resultant_report_available_notification_email(
    email: str,
    request: Request,
    resource: Resource,
    library_code: str,
) -> None:
    """
    Notifies an instructor that the resultant sheet is available.
    """
    front_domain = get_front_domain(request)
    project = resource.project
    tenant = request.tenant
    modal_url = f"{front_domain}/projects/{project.id}/?resource={resource.id}"

    subject = f"eplouribousse | {tenant.name} | {project.name} | {library_code} | {resource.code} | {_('resultant')}"

    email_content = render_to_string(
        "emails/notify_resultant_report_available.txt",
        {
            "resource_title": resource.title,
            "modal_url": modal_url,
        },
    )

    send_mail(
        subject=str(subject),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
        message=email_content,
    )
