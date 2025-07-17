from rest_framework.permissions import BasePermission

from epl.apps.project.models import Project, Role, Status
from epl.apps.user.models import User


class ProjectPermissions(BasePermission):
    def has_permission(self, request, view):
        match view.action:
            case "create":
                return bool(
                    request.user.is_authenticated & (request.user.is_superuser | request.user.is_project_creator)
                )
            case _:
                return True

    def has_object_permission(self, request, view, obj: Project) -> bool:
        if view.action in [
            "retrieve",
            "update",
            "partial_update",
            "destroy",
            "add_library",
            "update_status",
            "exclusion_reason",
            "remove_exclusion_reason",
            "status",
        ]:
            return self.user_has_permission(view.action, request.user, obj)
        if view.action == "validate":
            return self.user_has_permission("validate", request.user, obj)
        return True

    @staticmethod
    def compute_retrieve_permission(user: User, project: Project = None) -> bool:
        if project.status <= Status.READY:
            match project.status:
                case Status.DRAFT:
                    return user.project_roles.filter(project=project, role=Role.PROJECT_CREATOR).exists()
                case Status.REVIEW:
                    return user.project_roles.filter(project=project, role=Role.PROJECT_ADMIN).exists()
                case Status.READY:
                    return user.project_roles.filter(project=project, role=Role.PROJECT_MANAGER).exists()
        else:
            return not project.is_private

    @staticmethod
    def compute_update_permission(user: User, project: Project = None) -> bool:
        return user.project_roles.filter(
            project=project,
            role__in=[
                Role.PROJECT_ADMIN,
                Role.PROJECT_MANAGER,
            ],
        ).exists()

    @staticmethod
    def compute_create_permission(user: User, project: Project = None) -> bool:
        return user.project_roles.filter(project=project, role=Role.PROJECT_CREATOR).exists()

    @staticmethod
    def compute_add_library_permission(user: User, project: Project = None) -> bool:
        return user.project_roles.filter(
            project=project,
            role__in=[Role.PROJECT_ADMIN, Role.PROJECT_MANAGER, Role.PROJECT_CREATOR],
        ).exists()

    @staticmethod
    def compute_validate_permission(user: User, project: Project = None) -> bool:
        return user.project_roles.filter(project=project, role=Role.PROJECT_MANAGER).exists()

    @staticmethod
    def user_has_permission(action: str, user: User, project: Project = None) -> bool:
        if not user.is_authenticated:
            return False
        match action:
            case "create":
                return ProjectPermissions.compute_create_permission(user, project)
            case "retrieve":
                return ProjectPermissions.compute_retrieve_permission(user, project)
            case "update" | "partial_update":
                return ProjectPermissions.compute_update_permission(user, project)
            case "add_library":
                return ProjectPermissions.compute_add_library_permission(user, project)
            case "validate":
                return ProjectPermissions.compute_validate_permission(user, project)
            case _:
                return False
