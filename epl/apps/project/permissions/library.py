from rest_framework.permissions import BasePermission

from epl.apps.project.models.library import Library
from epl.apps.user.models import User


class LibraryPermission(BasePermission):
    def has_permission(self, request, view):
        match view.action:
            case "list" | "retrieve":
                return True
            case "create":
                return request.user.is_authenticated and (
                    request.user.is_superuser
                    or request.user.is_project_creator
                    or request.user.is_project_admin(project=None, search_for_any=True)
                )
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if view.action == "retrieve":
            return True
        if view.action in [
            "update",
            "partial_update",
            "destroy",
        ]:
            return self.user_has_permission(view.action, request.user, obj)
        return False

    @staticmethod
    def user_has_permission(action: str, user: User, obj: Library = None) -> bool:
        match action:
            case "update" | "partial_update" | "destroy":
                return (
                    user.is_superuser
                    or user.is_project_creator
                    or user.is_project_admin(project=None, search_for_any=True)
                )
        return False
