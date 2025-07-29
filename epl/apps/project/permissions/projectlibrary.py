from rest_framework.permissions import BasePermission


class ProjectLibraryPermissions(BasePermission):
    def has_permission(self, request, view):
        return view.action == "partial_update"

    def has_object_permission(self, request, view, obj):
        # obj is ProjectLibrary
        if view.action == "partial_update":
            user = request.user
            project = obj.project
            return user.is_project_creator or user.is_project_admin(project)
        return False
