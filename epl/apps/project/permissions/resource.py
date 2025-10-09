from rest_framework.permissions import BasePermission

from epl.apps.project.models import Resource
from epl.apps.user.models import User


class ResourcePermission(BasePermission):
    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj: Resource):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            # Allow read-only methods to anybody
            return True

        if view.action in [
            "retrieve",
            "update",
            "partial_update",
            "list_statuses",
            "collections",
            "validate_control",
            "report_anomalies",
            "reset_instruction",
        ]:
            return self.user_has_permission(view.action, request.user, obj)

        return False

    @staticmethod
    def user_has_permission(action: str, user: User, resource: Resource) -> bool:
        match action:
            case "create":
                # Resources only created through import
                return False
            case "retrieve" | "list_statuses":
                # Anybody can view a resource
                return True
            case "update" | "partial_update":
                return False
            case "destroy":
                return bool(user and user.is_authenticated and user.is_project_creator)
            case "collections":
                return True
            case "validate_control":
                return bool(user and user.is_authenticated and user.is_controller(resource.project))
            case "report_anomalies":
                # user is controller or instructor for the project
                return bool(
                    user
                    and user.is_authenticated
                    and (user.is_controller(resource.project) or user.is_instructor(resource.project))
                )
            case "reset_instruction":
                return bool(user and user.is_authenticated and user.is_project_admin(resource.project))

        return False
