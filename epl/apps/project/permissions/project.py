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
    def user_has_permission(action: str, user: User, project: Project = None) -> bool:
        match action:
            case "retrieve":
                if project.is_private:
                    return True
                else:
                    match project.status:
                        case Status.DRAFT:
                            return user.project_roles.filter(project=project, role=Role.PROJECT_CREATOR).exists()
                        case Status.REVIEW:
                            return user.project_roles.filter(project=project, role=Role.PROJECT_ADMIN).exists()
                        case Status.READY:
                            return user.project_roles.filter(project=project, role=Role.PROJECT_MANAGER).exists()
                        case _:
                            return True
            case "update" | "partial_update":
                return user.project_roles.filter(
                    project=project,
                    role__in=[
                        Role.PROJECT_ADMIN,
                        Role.PROJECT_MANAGER,
                    ],
                ).exists()
            case "create":
                return user.project_roles.filter(project=project, role=Role.PROJECT_CREATOR).exists()
            case "add_library":
                return user.project_roles.filter(
                    project=project,
                    role__in=[Role.PROJECT_ADMIN, Role.PROJECT_MANAGER, Role.PROJECT_CREATOR],
                ).exists()
            case "validate":
                return user.is_superuser
            case _:
                return False
