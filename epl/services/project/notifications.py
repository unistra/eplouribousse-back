from epl.apps.project.models import Project, Resource, Role, UserRole
from epl.apps.project.models.choices import AlertType
from epl.apps.project.models.collection import Arbitration, Collection
from epl.apps.user.models import User
from epl.services.user.email import (
    send_anomaly_notification_email,
    send_arbitration_notification_email,
    send_collection_positioned_email,
    send_control_notification_email,
    send_instruction_turn_email,
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
    Notifie les instructeurs concernés par un cas d'arbitrage (type 0 ou 1).
    """
    # check project settings to see if arbitration emails should be sent
    # to avoid unnecessary queries if arbitration is disabled
    project_alerts = resource.project.settings.get("alerts", {})
    if project_alerts.get(AlertType.ARBITRATION.value, True) is False:
        return

    arbitration_type = resource.arbitration
    library_ids_to_notify = []

    match arbitration_type:
        case Arbitration.ONE:
            library_ids_to_notify = resource.collections.filter(position=1).values_list("library_id", flat=True)

        case Arbitration.ZERO:
            # Every resource instructor has to be notified, except those with position (excluded collection)
            library_ids_to_notify = resource.collections.filter(position__gt=0).values_list("library_id", flat=True)

        case _:
            return

    instructors_to_notify = (
        UserRole.objects.filter(project=resource.project, role=Role.INSTRUCTOR, library_id__in=library_ids_to_notify)
        .select_related("user", "library")
        .distinct()  # prevent sending multiple emails to the same user if the code eventually evolves.
    )

    for instructor in instructors_to_notify:
        if should_send_alert(instructor.user, resource.project, AlertType.ARBITRATION):
            send_arbitration_notification_email(
                email=instructor.user.email,
                request=request,
                resource=resource,
                library_code=instructor.library.code,
                arbitration_type=arbitration_type,
            )


def notify_other_instructors_of_positioning(resource: Resource, request, positioned_collection) -> None:
    """
    Notifies instructors who have not yet positioned their collection for a given resource.
    It excludes:
    - The user who performed the action.
    - Any instructor who has already positioned their collection for this resource.
    """
    # check project settings to see if arbitration emails should be sent
    # to avoid unnecessary queries if arbitration is disabled
    project_alerts = resource.project.settings.get("alerts", {})
    if project_alerts.get(AlertType.POSITIONING.value, True) is False:
        return

    acting_user = request.user

    unpositioned_library_ids = resource.collections.filter(position__isnull=True).values_list("library_id", flat=True)

    instructors_to_notify = (
        UserRole.objects.filter(
            project=resource.project,
            role=Role.INSTRUCTOR,
            library_id__in=unpositioned_library_ids,
        )
        .select_related("user")
        .distinct()
    )

    for instructor_role in instructors_to_notify:
        if instructor_role.user == acting_user:  # double-check that the user is not already positioned.
            continue

        if should_send_alert(instructor_role.user, resource.project, AlertType.POSITIONING):
            send_collection_positioned_email(
                email=instructor_role.user.email,
                request=request,
                resource=resource,
                positioned_collection=positioned_collection,
            )


def notify_instructors_of_instruction_turn(resource: Resource, collection: Collection, request):
    """
    Notifies the instructors of a library that it is their turn to instruct.
    """
    project = resource.project
    library = collection.library

    # check project settings to see if arbitration emails should be sent
    # to avoid unnecessary queries if arbitration is disabled
    project_alerts = resource.project.settings.get("alerts", {})
    if project_alerts.get(AlertType.INSTRUCTION.value, True) is False:
        return

    # Find the instructors of the collection that has to be instructed.
    instructors_to_notify = (
        UserRole.objects.filter(project=project, role=Role.INSTRUCTOR, library=library)
        .select_related("user")
        .distinct()
    )

    for instructor_to_notify in instructors_to_notify:
        if should_send_alert(instructor_to_notify.user, resource.project, AlertType.INSTRUCTION):
            send_instruction_turn_email(
                email=instructor_to_notify.user.email,
                request=request,
                resource=resource,
                library_code=library.code,
            )


def notify_controllers_of_control(resource, request, cycle):
    """
    Notifies controllers (role CONTROLLER) at the end of the instruction cycle.
    """
    project = resource.project
    # check project settings to see if arbitration emails should be sent
    # to avoid unnecessary queries if arbitration is disabled
    project_alerts = resource.project.settings.get("alerts", {})
    if project_alerts.get(AlertType.CONTROL.value, True) is False:
        return
    controllers = UserRole.objects.filter(project=project, role=Role.CONTROLLER).select_related("user").distinct()

    for controller in controllers:
        if should_send_alert(controller.user, resource.project, AlertType.CONTROL):
            send_control_notification_email(
                email=controller.user.email,
                request=request,
                resource=resource,
                cycle=cycle,
            )


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

    # Check project settings to see if anomaly emails should be sent
    project_alerts = resource.project.settings.get("alerts", {})
    if project_alerts.get(AlertType.ANOMALY.value, True) is False:
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
            instructor_role.user, project, AlertType.ANOMALY
        ):
            recipients.add(instructor_role.user.email)

    # Get project administrators
    project_admins = UserRole.objects.filter(project=project, role=Role.PROJECT_ADMIN).select_related("user").distinct()

    for admin_role in project_admins:
        if should_send_alert(admin_role.user, project, AlertType.ANOMALY):
            recipients.add(admin_role.user.email)

    # Get other controllers (excluding the reporter if he's a controller)
    controllers = UserRole.objects.filter(project=project, role=Role.CONTROLLER).select_related("user").distinct()

    for controller_role in controllers:
        if controller_role.user != reporter_user and should_send_alert(
            controller_role.user, project, AlertType.ANOMALY
        ):
            recipients.add(controller_role.user.email)

    # Add copy to sender
    if should_send_alert(reporter_user, project, AlertType.ANOMALY):
        recipients.add(reporter_user.email)

    # Send emails to all recipients
    for email in recipients:
        send_anomaly_notification_email(email=email, request=request, resource=resource, reporter_user=reporter_user)
