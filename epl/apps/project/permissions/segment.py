from rest_framework.permissions import BasePermission

from epl.apps.project.models import Collection, Segment
from epl.apps.user.models import User


class SegmentPermissions(BasePermission):
    def has_permission(self, request, view):
        match view.action:
            case "create":
                try:
                    collection = Collection.objects.get(pk=request.data.get("collection"))
                    return request.user.is_authenticated and self.is_user_instructor(
                        collection=collection, user=request.user
                    )
                except Collection.DoesNotExist:
                    return False
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
                return SegmentPermissions.is_user_instructor(collection=segment.collection, user=user)
            case "up" | "down":
                return SegmentPermissions.is_user_instructor(
                    collection=segment.collection, user=user
                ) or SegmentPermissions.is_user_admin(collection=segment.collection, user=user)
            case _:
                return False

    @staticmethod
    def is_user_instructor(collection: Collection, user: User) -> bool:
        return user.is_instructor(project=collection.project, library=collection.library)

    @staticmethod
    def is_user_admin(collection: Collection, user: User) -> bool:
        return user.is_project_admin(project=collection.project)
