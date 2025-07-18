from django.db import models
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
    def compute_validate_permission(user: User, project: Project = None) -> bool:
        return user.project_roles.filter(project=project, role=Role.PROJECT_MANAGER).exists()

    def compute_update_status_permission(user: User, project: Project = None) -> bool:
        match project.status:
            case Status.DRAFT:
                return user.is_project_creator
            case Status.REVIEW:
                return user.project_roles.filter(project=project, role=Role.PROJECT_ADMIN).exists()
            case Status.READY | Status.POSITIONING | Status.INSTRUCTION_BOUND | Status.INSTRUCTION_UNBOUND:
                return user.project_roles.filter(project=project, role=Role.PROJECT_MANAGER).exists()
            case _:
                return False

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
            case "validate":
                return ProjectPermissions.compute_validate_permission(user, project)
            case "update_status":
                return True
            case "exclusion_reason" | "remove_exclusion_reason" | "add_library":
                return user.project_roles.filter(
                    models.Q(project=project, role=Role.PROJECT_ADMIN) | models.Q(role=Role.PROJECT_CREATOR)
                ).exists()
            case _:
                return False
