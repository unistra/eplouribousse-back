from rest_framework.permissions import SAFE_METHODS, BasePermission

from epl.apps.project.models.library import Library
from epl.apps.user.models import User


class LibraryPermission(BasePermission):
    def has_permission(self, request, view):
        match view.action:
            case "create" | "list":
                return bool(request.user and self.user_has_permission(view.action, request.user))
            case _:
                return bool(request.user and request.user.is_authenticated)
        return False

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)

        if view.action in ["update", "partial_update", "destroy"]:
            return bool(request.user and self.user_has_permission(view.action, request.user, obj))
        return False

    @staticmethod
    def user_has_permission(action: str, user: User, obj: Library = None) -> bool:
        match action:
            case "create" | "update" | "partial_update" | "destroy":
                return user.is_authenticated and user.is_project_creator
            case "list" | "retrieve":
                return user.is_authenticated
            case _:
                return False
