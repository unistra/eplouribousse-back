from rest_framework.permissions import BasePermission

from epl.apps.project.models import Collection, Segment
from epl.apps.user.models import User


class SegmentPermissions(BasePermission):
    def has_permission(self, request, view):
        match view.action:
            case "create":
                project = Collection.objects.get(id=request.data.get("collection")).project
                return request.user.is_authenticated and request.user.is_instructor(project=project)
            case _:
                return True

    def has_object_permission(self, request, view, obj: Segment) -> bool:
        if view.action in []:
            return self.user_has_permission(view.action, request.user, obj)
        return False

    @staticmethod
    def user_has_permission(action: str, user: User, project: Segment = None) -> bool:
        if not user.is_authenticated:
            return False
        match action:
            case _:
                return False
