from rest_framework import permissions
from rest_framework.permissions import SAFE_METHODS

from epl.apps.project.models import Collection
from epl.apps.user.models import User


class CollectionPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)

        match view.action:
            case "create" | "update" | "partial_update" | "destroy" | "import_csv":
                return bool(request.user and self.user_has_permission(view.action, request.user, obj))

        return False

    @staticmethod
    def user_has_permission(action: str, user: User, obj: Collection) -> bool:
        match action:
            case "import_csv":
                return bool(user and user.is_authenticated and user.is_project_creator)
            case "create" | "update" | "partial_update" | "destroy":
                return False

        return False
