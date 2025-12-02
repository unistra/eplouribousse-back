from rest_framework import permissions
from rest_framework.permissions import SAFE_METHODS

from epl.apps.project.models import Collection
from epl.apps.user.models import User


class CollectionPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)

        match view.action:
            case (
                "create"
                | "update"
                | "partial_update"
                | "destroy"
                | "import_csv"
                | "bulk_delete"
                | "position"
                | "exclude"
                | "comment_positioning"
                | "position"
                | "finish_instruction_turn"
            ):
                return bool(request.user and self.user_has_permission(view.action, request.user, obj))

        return False

    @staticmethod
    def user_has_permission(action: str, user: User, obj: Collection) -> bool:
        match action:
            case "position":
                return bool(
                    user and user.is_authenticated and user.is_instructor(project=obj.project, library=obj.library)
                )
            case "finish_instruction_turn":
                return bool(
                    user and user.is_authenticated and user.is_instructor(project=obj.project, library=obj.library)
                )
            case "comment_positioning":
                return bool(
                    user and user.is_authenticated and user.is_instructor(project=obj.project, library=obj.library)
                )
            case "import_csv" | "bulk_delete":
                return bool(user and user.is_authenticated and user.is_project_creator)
            case "update" | "partial_update" | "position" | "exclude":
                return bool(user and user.is_authenticated and user.is_instructor(obj.project, obj.library))
            case "destroy":
                return bool(user and user.is_authenticated and user.is_project_creator)
            case "create":
                return False

        return False
