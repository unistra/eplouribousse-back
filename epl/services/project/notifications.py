from epl.apps.project.models import Project, Role
from epl.apps.user.models import User
from epl.services.user.email import (
    send_invite_project_admins_to_review_email,
    send_invite_project_managers_to_launch_email,
    send_invite_to_epl_email,
    send_project_launched_email,
)


def invite_unregistered_users_to_epl(project: Project, request):
    """
    Parse the invitations to join epl (stored in project.invitations) and sends an email for each one.
    This function is intended to be called when the project goes from "DRAFT" into "REVIEW".
    """
    from epl.apps.user.views import _get_invite_signer

    invitations_list = project.invitations or []

    for invitation in invitations_list:
        email = invitation.get("email")
        if not email:
            continue

        send_invite_to_epl_email(
            email=email,
            request=request,
            signer=_get_invite_signer(),
            project_id=str(project.id),
            library_id=invitation.get("library_id"),
            role=invitation.get("role"),
            assigned_by_id=request.user.id,
        )


def invite_project_admins_to_review(project: Project, request):
    """
    Email project admins when a project is ready for review.
    This function is intended to be called:
     - when the project goes from "DRAFT" into "REVIEW",
     - and the user with a role of PROJECT_ADMIN is already registered in the database.
    """

    project_admins = User.objects.filter(
        project_roles__project=project,
        project_roles__role=Role.PROJECT_ADMIN,
    )

    tenant_name = request.tenant.name
    # Guard against AnonymousUser which has no email.
    # We consider that the user who sent the request is the creator of the project.
    project_creator_email = (
        request.user.email if getattr(request.user, "is_authenticated", False) and request.user.email else None
    )

    for project_admin in project_admins:
        send_invite_project_admins_to_review_email(
            email=project_admin.email,
            request=request,
            project_name=project.name,
            tenant_name=tenant_name,
            project_creator_email=project_creator_email,
        )


def invite_project_managers_to_launch(project: Project, request):
    """
    Email project pilots when a project is ready for launch.
    This function is intended to be called:
     - when the project goes from "REVIEW" into "READY",
     - and the user with a role of PROJECT_PILOT is already registered in the database.
    """

    project_managers = User.objects.filter(
        project_roles__project=project,
        project_roles__role=Role.PROJECT_MANAGER,
    )

    tenant_name = request.tenant.name
    # Guard against AnonymousUser which has no email.
    # We consider that the user who sent the request is the creator of the project.
    project_creator_email = (
        request.user.email if getattr(request.user, "is_authenticated", False) and request.user.email else None
    )

    for project_manager in project_managers:
        send_invite_project_managers_to_launch_email(
            email=project_manager.email,
            request=request,
            project_name=project.name,
            tenant_name=tenant_name,
            project_creator_email=project_creator_email,
        )


def notify_project_launched(project: Project, request, is_starting_now: bool):
    project_users = User.objects.filter(
        project_roles__project=project,
    ).distinct()

    send_project_launched_email(
        request=request,
        project=project,
        project_users=[user.email for user in project_users],
        is_starting_now=is_starting_now,
    )
