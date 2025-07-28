from django.db import models
from rest_framework.permissions import BasePermission

from epl.apps.project.models import Project, ProjectStatus, Role
from epl.apps.user.models import User


class ProjectPermissions(BasePermission):
    def has_permission(self, request, view):
        match view.action:
            case "create":
                return bool(request.user.is_authenticated and request.user.is_project_creator)
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
            "launch",
        ]:
            return self.user_has_permission(view.action, request.user, obj)
        if view.action == "validate":
            return self.user_has_permission("validate", request.user, obj)
        return True

    @staticmethod
    def compute_retrieve_permission(user: User, project: Project = None) -> bool:
        permission_checks = [
            (ProjectStatus.DRAFT, lambda: user.is_project_creator),
            (ProjectStatus.REVIEW, lambda: user.is_project_admin(project=project)),
            (ProjectStatus.READY, lambda: user.is_project_manager(project=project)),
            (
                ProjectStatus.LAUNCHED,
                lambda: user.is_controller(project=project)
                or user.is_instructor(project=project)
                or user.is_guest(project=project),
            ),
        ]

        for status, check in permission_checks:
            if project.status >= status and check():
                return True

        return not project.is_private

    @staticmethod
    def compute_update_permission(user: User) -> bool:
        return user.is_project_creator

    @staticmethod
    def compute_validate_permission(user: User, project: Project = None) -> bool:
        return user.project_roles.filter(project=project, role=Role.PROJECT_MANAGER).exists()

    @staticmethod
    def compute_update_status_permission(user: User, project: Project = None) -> bool:
        if user.is_superuser:
            return True

        if user.is_project_creator:
            return project.status >= ProjectStatus.DRAFT
        if user.is_project_admin(project=project):
            return project.status >= ProjectStatus.REVIEW
        if user.is_project_manager(project=project):
            return project.status >= ProjectStatus.READY

        return False

    @staticmethod
    def user_has_permission(action: str, user: User, project: Project = None) -> bool:
        if not user.is_authenticated:
            return False
        match action:
            case "retrieve":
                return ProjectPermissions.compute_retrieve_permission(user, project)
            case "update" | "partial_update":
                return ProjectPermissions.compute_update_permission(user)
            case "validate":
                return ProjectPermissions.compute_validate_permission(user, project)
            case "update_status":
                return True
            case "exclusion_reason" | "remove_exclusion_reason" | "add_library":
                return user.project_roles.filter(
                    models.Q(project=project, role=Role.PROJECT_ADMIN) | models.Q(role=Role.PROJECT_CREATOR)
                ).exists()
            case "launch":
                return user.is_project_manager(project=project)
            case _:
                return False
