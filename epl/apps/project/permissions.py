from rest_framework.permissions import SAFE_METHODS, BasePermission

from epl.apps.project.models import Project, UserRole
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
        if request.method in SAFE_METHODS:
            return True
        if view.action in ["update", "partial_update", "delete"]:
            return self.user_has_permission(view.action, request.user, obj)
        if view.action == "validate":
            return self.user_has_permission("validate", request.user, obj)
        return True

    @staticmethod
    def user_has_permission(action: str, user: User, project: Project = None) -> bool:
        match action:
            case "list" | "view":
                return True
            case "update" | "partial_update":
                return user.project_roles.filter(
                    project=project,
                    role__in=[
                        UserRole.Role.PROJECT_ADMIN,
                        UserRole.Role.PROJECT_MANAGER,
                    ],
                ).exists()
            case "create":
                return user.project_roles.filter(project=project, role=UserRole.Role.PROJECT_CREATOR).exists()
            case "validate":
                return user.is_superuser
            case _:
                return False
