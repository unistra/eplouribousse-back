from collections import defaultdict
from typing import Any

from django.conf import settings
from django.core.mail import EmailMessage, send_mass_mail

from epl.apps.project.models import Library, Project, Resource, Role, UserRole
from epl.apps.project.models.choices import AlertType
from epl.apps.project.models.collection import Arbitration, Collection
from epl.apps.user.models import User
from epl.apps.user.views import _get_invite_signer
from epl.services.user.email import (
    prepare_anomaly_notification_email,
    prepare_anomaly_resolved_notification_email,
    prepare_arbitration_notification_email,
    prepare_collection_positioned_email,
    prepare_control_notification_email,
    prepare_instruction_turn_email,
    prepare_resultant_report_available_email,
    send_invite_project_admins_to_review_email,
    send_invite_project_managers_to_launch_email,
    send_invite_to_epl_email,
    send_project_launched_email,
)


def should_send_alert(user: User, project: Project, alert_type: AlertType) -> bool:
    """
    Checks if an alert should be sent to a user, according to their own settings and the project's settings.
    If the alert is deactivated in the project, it is not sent to the user.
    If the alert is activated in the project, the user can deactivate it in their settings.
    """
    # checks alert settings in Project model
    admin_alerts = project.settings.get("alerts", {})
    if admin_alerts.get(alert_type.value, True) is False:
        return False
    # checks alert settings in User model
    user_alerts = user.settings.get("alerts", {})
    user_alerts_for_project = user_alerts.get(str(project.id), {})
    return user_alerts_for_project.get(alert_type.value, True)


def group_invitations_by_email(invitations: list[dict[str, Any]] | None) -> dict[str, list[dict[str, Any]]]:
    """
    Group invitations by email.
    Takes a list of invitations (dict) and returns a dict where the keys are the email addresses and the values are the corresponding invitations.
    Allows to process invitations if a user has multiple invitations, for multiple role in a project.
    """
    invitations_by_email = defaultdict(list)

    for invitation in invitations or []:
        email = invitation.get("email")
        if email and isinstance(email, str):
            cleaned_email = email.strip()
            if cleaned_email:
                invitations_by_email[cleaned_email].append(invitation)

    return dict(invitations_by_email)


def invite_unregistered_users_to_epl(project: Project, request):
    """
    Parse the invitations to join epl (stored in project.invitations) and sends an email for each one.
    This function is intended to be called when the project goes from "DRAFT" into "REVIEW".
    """
    invitations_grouped_by_email = group_invitations_by_email(project.invitations)

    for email, user_invitations in invitations_grouped_by_email.items():
        try:
            # Check if user already exists in database
            existing_user = User.objects.active().get(email=email)

            # User exists, add them directly to the project with their roles
            for invitation in user_invitations:
                role = invitation.get("role")
                library_id = invitation.get("library_id")

                # Create UserRole directly using the same logic as AssignRoleSerializer
                UserRole.objects.get_or_create(
                    user=existing_user,
                    role=role,
                    library_id=library_id,
                    project=project,
                    defaults={
                        "assigned_by": request.user,
                    },
                )

        except User.DoesNotExist:
            # User doesn't exist, send invitation email
            send_invite_to_epl_email(
                email=email,
                request=request,
                signer=_get_invite_signer(),
                project_id=str(project.id),
                invitations=user_invitations,
                assigned_by_id=request.user.id,
            )


def invite_single_user_to_epl(project: Project, invitation: dict[str, Any], request):
    """
    Invite a single user to epl based on a specific invitation.
    Allows sending invitation emails even if a project is no longer in "DRAFT" state.
    """
    email = invitation.get("email")
    if not email:
        return

    cleaned_email = email.strip()
    if not cleaned_email:
        return

    try:
        # Check if user already exists in database
        existing_user = User.objects.active().get(email=cleaned_email)

        # User exists, add them directly to the project with their role
        role = invitation.get("role")
        library_id = invitation.get("library_id")

        # Create UserRole directly
        UserRole.objects.get_or_create(
            user=existing_user,
            role=role,
            library_id=library_id,
            project=project,
            defaults={
                "assigned_by": request.user,
            },
        )

    except User.DoesNotExist:
        # User doesn't exist, send invitation email
        send_invite_to_epl_email(
            email=cleaned_email,
            request=request,
            signer=_get_invite_signer(),
            project_id=str(project.id),
            invitations=[invitation],
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

    admin_email = (
        request.user.email if getattr(request.user, "is_authenticated", False) and request.user.email else None
    )
    for project_manager in project_managers:
        send_invite_project_managers_to_launch_email(
            email=project_manager.email,
            request=request,
            project=project,
            tenant_name=tenant_name,
            action_user_email=admin_email,
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


def notify_instructors_of_arbitration(resource: Resource, request):
    """
    Notifies instructors concerned by an arbitration case (type 0 or 1).
    """
    project = resource.project
    # Avoid unnecessary queries if notifications are already disabled at the project level.
    project_alerts = project.settings.get("alerts", {})
    if project_alerts.get(AlertType.ARBITRATION.value, True) is False:
        return

    arbitration_type = resource.arbitration
    library_ids_to_notify = []

    match arbitration_type:
        case Arbitration.ONE:
            library_ids_to_notify = resource.collections.filter(position=1).values_list("library_id", flat=True)
        case Arbitration.ZERO:
            library_ids_to_notify = resource.collections.filter(position__gt=0).values_list("library_id", flat=True)
        case _:
            return

    instructors_to_notify = (
        UserRole.objects.filter(project=project, role=Role.INSTRUCTOR, library_id__in=library_ids_to_notify)
        .select_related("user", "library")
        .distinct()  # prevent sending multiple emails to the same user if the code eventually evolves.
    )

    messages = []
    for instructor in instructors_to_notify:
        if should_send_alert(instructor.user, project, AlertType.ARBITRATION):
            messages.append(
                prepare_arbitration_notification_email(
                    email=instructor.user.email,
                    request=request,
                    resource=resource,
                    library_code=instructor.library.code,
                    arbitration_type=arbitration_type,
                )
            )

    if messages:
        send_mass_mail(messages, fail_silently=False)


def notify_other_instructors_of_positioning(resource: Resource, request, positioned_collection) -> None:
    """
    Notifies instructors who have not yet positioned their collection for a given resource.
    It excludes:
    - The user who performed the action.
    - Any instructor who has already positioned their collection for this resource.
    """
    project = resource.project
    # Avoid unnecessary queries if notifications are already disabled at the project level.
    project_alerts = project.settings.get("alerts", {})
    if project_alerts.get(AlertType.POSITIONING.value, True) is False:
        return

    unpositioned_library_ids = resource.collections.filter(position__isnull=True).values_list("library_id", flat=True)

    instructors_to_notify = (
        UserRole.objects.filter(
            project=project,
            role=Role.INSTRUCTOR,
            library_id__in=unpositioned_library_ids,
        )
        .select_related("user")
        .distinct()
    )

    messages = []
    for instructor_role in instructors_to_notify:
        if should_send_alert(instructor_role.user, project, AlertType.POSITIONING):
            messages.append(
                prepare_collection_positioned_email(
                    email=instructor_role.user.email,
                    request=request,
                    resource=resource,
                    library_code=instructor_role.library.code,
                    positioned_collection=positioned_collection,
                )
            )

    if messages:
        send_mass_mail(messages, fail_silently=False)


def notify_instructors_of_instruction_turn(resource: Resource, library: Library, request):
    """
    Notifies the instructors of a library that it is their turn to instruct.
    """
    project = resource.project

    # Avoid unnecessary queries if notifications are already disabled at the project level.
    project_alerts = project.settings.get("alerts", {})
    if project_alerts.get(AlertType.INSTRUCTION.value, True) is False:
        return

    instructors_to_notify = (
        UserRole.objects.filter(project=project, role=Role.INSTRUCTOR, library=library)
        .select_related("user")
        .distinct()
    )

    messages = []
    for instructor in instructors_to_notify:
        if should_send_alert(instructor.user, project, AlertType.INSTRUCTION):
            messages.append(
                prepare_instruction_turn_email(
                    email=instructor.user.email,
                    request=request,
                    resource=resource,
                    library_code=library.code,
                )
            )

    if messages:
        send_mass_mail(messages, fail_silently=False)


def notify_controllers_of_control(resource, request, cycle):
    """
    Notifies controllers (role CONTROLLER) at the end of the instruction cycle.
    """
    project = resource.project
    # Avoid unnecessary queries if notifications are already disabled at the project level.
    project_alerts = project.settings.get("alerts", {})
    if project_alerts.get(AlertType.CONTROL.value, True) is False:
        return

    controllers = UserRole.objects.filter(project=project, role=Role.CONTROLLER).select_related("user").distinct()

    recipients = set()
    for controller in controllers:
        if should_send_alert(controller.user, project, AlertType.CONTROL):
            recipients.add(controller.user.email)

    if recipients:
        subject, body = prepare_control_notification_email(
            request=request,
            resource=resource,
            cycle=cycle,
        )

        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=list(recipients),
        )
        email.send(fail_silently=False)


def notify_anomaly_reported(resource: Resource, request, reporter_user: User):
    """
    Sends notification emails when anomalies are reported on a resource.

    Recipients:
    - Instructors concerned by the resource instruction (excluding those with excluded collections)
    - Project administrators
    - Other controllers
    - Copy to the sender (reporter)
    """
    project = resource.project

    # Avoid unnecessary queries if notifications are already disabled at the project level.
    project_alerts = project.settings.get("alerts", {})
    if project_alerts.get(AlertType.INSTRUCTION.value, True) is False:
        return

    recipients = set()

    # Get instructors concerned by the resource instruction (excluding those with excluded collections)
    instructors_to_notify = (
        UserRole.objects.filter(
            project=project,
            role=Role.INSTRUCTOR,
            library__collections__resource=resource,
        )
        .exclude(
            library__collections__position=0  # Exclude excluded collections
        )
        .select_related("user")
        .distinct()
    )

    for instructor_role in instructors_to_notify:
        # Exclude the instructor who reported the anomaly (he will receive a copy later)
        if instructor_role.user != reporter_user and should_send_alert(
            instructor_role.user, project, AlertType.INSTRUCTION
        ):
            recipients.add(instructor_role.user.email)

    # Get project administrators
    project_admins = UserRole.objects.filter(project=project, role=Role.PROJECT_ADMIN).select_related("user").distinct()

    for admin_role in project_admins:
        if should_send_alert(admin_role.user, project, AlertType.INSTRUCTION):
            recipients.add(admin_role.user.email)

    # Get other controllers (excluding the reporter if he's a controller)
    controllers = UserRole.objects.filter(project=project, role=Role.CONTROLLER).select_related("user").distinct()

    for controller_role in controllers:
        if controller_role.user != reporter_user and should_send_alert(
            controller_role.user, project, AlertType.INSTRUCTION
        ):
            recipients.add(controller_role.user.email)

    # Add copy to sender
    if should_send_alert(reporter_user, project, AlertType.INSTRUCTION):
        recipients.add(reporter_user.email)

    # Prepare all emails and send in one SMTP connection
    if recipients:
        messages = [
            prepare_anomaly_notification_email(
                email=email, request=request, resource=resource, reporter_user=reporter_user
            )
            for email in recipients
        ]
        send_mass_mail(messages)


def _get_to_recipients_for_anomaly_resolved(project, current_turn_collections):
    """
    Helper for notify_anomaly_resolved.
    Get instructors with turn + project admins for TO field.
    """
    to_recipients = set()

    # Get instructors whose turn has come
    for collection in current_turn_collections:
        instructors_with_turn = UserRole.objects.filter(
            project=project,
            role=Role.INSTRUCTOR,
            library=collection.library,
        ).select_related("user")

        for instructor_role in instructors_with_turn:
            if should_send_alert(instructor_role.user, project, AlertType.INSTRUCTION):
                to_recipients.add(instructor_role.user.email)

    # Get project administrators
    project_admins = UserRole.objects.filter(project=project, role=Role.PROJECT_ADMIN).select_related("user").distinct()

    for admin_role in project_admins:
        if should_send_alert(admin_role.user, project, AlertType.INSTRUCTION):
            to_recipients.add(admin_role.user.email)

    return to_recipients


def _get_cc_recipients_for_anomaly_resolved(project, resource, current_turn_collections):
    """
    Helper for notify_anomaly_resolved.
    Get other instructors (not with turn, not excluded) for CC field.
    """
    cc_recipients = set()
    other_instructors = (
        UserRole.objects.filter(
            project=project,
            role=Role.INSTRUCTOR,
            library__collections__resource=resource,
        )
        .exclude(library__collections__position=0)
        .exclude(library__in=[collection.library for collection in current_turn_collections])
        .select_related("user")
        .distinct()
    )

    for instructor_role in other_instructors:
        if should_send_alert(instructor_role.user, project, AlertType.INSTRUCTION):
            cc_recipients.add(instructor_role.user.email)

    return cc_recipients


def notify_anomaly_resolved(resource: Resource, request, admin_user: User):
    """
    Sends notification emails when anomalies are resolved by a project administrator.

    Recipients:
    - TO: Instructors whose turn has come to instruct + Project administrators
    - CC: Other instructors concerned by the resource instruction
    """
    project = resource.project

    project_alerts = project.settings.get("alerts", {})
    if project_alerts.get(AlertType.INSTRUCTION.value, True) is False:
        return

    # Get the current turn
    next_turn = resource.next_turn
    current_turn_collections = []
    library_codes_with_turn = []

    if next_turn:
        try:
            current_collection = resource.collections.get(id=next_turn["collection"])
            current_turn_collections = [current_collection]
            library_codes_with_turn = [current_collection.library.code]
        except Collection.DoesNotExist:
            pass

    # Collect TO and CC recipients
    to_recipients = _get_to_recipients_for_anomaly_resolved(project, current_turn_collections)
    cc_recipients = _get_cc_recipients_for_anomaly_resolved(project, resource, current_turn_collections)

    # Send email
    if to_recipients:
        library_codes_str = ", ".join(library_codes_with_turn) if library_codes_with_turn else "N/A"
        email_message = prepare_anomaly_resolved_notification_email(
            to_emails=list(to_recipients),
            cc_emails=list(cc_recipients),
            request=request,
            resource=resource,
            library_code=library_codes_str,
            admin_user=admin_user,
        )
        email_message.send(fail_silently=False)


def notify_resultant_report_available(resource: Resource, request) -> None:
    """
    Notify instructors that the resultant sheet is available.
    Instructors with excluded collections should not receive the email.
    """
    project = resource.project

    project_alerts = project.settings.get("alerts", {})
    if project_alerts.get(AlertType.EDITION.value, True) is False:
        return

    instructors_to_notify = (
        UserRole.objects.filter(
            project=project,
            role=Role.INSTRUCTOR,
            library__collections__resource=resource,
            library__collections__position__gt=0,
        )
        .select_related("user", "library")
        .distinct()
    )

    messages = []
    for instructor in instructors_to_notify:
        if should_send_alert(instructor.user, project, AlertType.EDITION):
            messages.append(
                prepare_resultant_report_available_email(
                    email=instructor.user.email,
                    request=request,
                    resource=resource,
                    library_code=instructor.library.code,
                )
            )

    if messages:
        send_mass_mail(messages, fail_silently=False)
