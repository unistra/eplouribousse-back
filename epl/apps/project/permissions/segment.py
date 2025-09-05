from rest_framework.permissions import BasePermission

from epl.apps.project.models import Collection, Segment
from epl.apps.user.models import User


class SegmentPermissions(BasePermission):
    def has_permission(self, request, view):
        match view.action:
            case "create":
                return request.user.is_authenticated and self.is_user_instructor(
                    collection_id=request.data.get("collection"), user=request.user
                )
            case _:
                return True

    def has_object_permission(self, request, view, obj: Segment) -> bool:
        if view.action in [
            "partial_update",
            "destroy",
            "up",
            "down",
        ]:
            return self.user_has_permission(view.action, request.user, obj)
        return False

    @staticmethod
    def user_has_permission(action: str, user: User, segment: Segment = None) -> bool:
        if not user.is_authenticated:
            return False
        match action:
            case "partial_update" | "destroy":
                return SegmentPermissions.is_user_instructor(collection_id=segment.collection.id, user=user)
            case "up" | "down":
                return SegmentPermissions.is_user_instructor(
                    collection_id=segment.collection.id, user=user
                ) or SegmentPermissions.is_user_controller(collection_id=segment.collection.id, user=user)
            case _:
                return False

    @staticmethod
    def is_user_instructor(collection_id: str, user: User) -> bool:
        project = Collection.objects.get(id=collection_id).project
        return user.is_instructor(project=project)

    @staticmethod
    def is_user_controller(collection_id: str, user: User) -> bool:
        project = Collection.objects.get(id=collection_id).project
        return user.is_controller(project=project)
