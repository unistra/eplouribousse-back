from rest_framework.permissions import BasePermission


class ProjectStatusPermissions(BasePermission):
    def has_permission(self, request, view):
        # todo : Implement a more specific permission check if needed
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        # todo : Implement a more specific permission check if needed
        return bool(request.user and request.user.is_authenticated)
