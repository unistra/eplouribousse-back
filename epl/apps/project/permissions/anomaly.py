from rest_framework.permissions import BasePermission

from epl.apps.project.models import Anomaly


class AnomalyPermissions(BasePermission):
    def has_permission(self, request, view) -> bool:
        if view.action == "list":
            return True
        return False

    def has_object_permission(self, request, view, obj: Anomaly) -> bool:
        return False

    @staticmethod
    def user_has_permission(action: str, user, anomaly: Anomaly = None) -> bool:
        return False
