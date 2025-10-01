from django.db.models import Q, Subquery
from rest_framework.permissions import BasePermission

from epl.apps.project.models import Anomaly, Library, Role, Segment, UserRole
from epl.apps.user.models import User


class AnomalyPermissions(BasePermission):
    def has_permission(self, request, view) -> bool:
        if view.action == "list":
            return True
        if view.action == "create":
            # In fact, it's more complicated, we just check if the user is authenticated here.
            # More detailed permission check is done in the viewset's create method.
            return bool(request.user and request.user.is_authenticated)
        return True

    def has_object_permission(self, request, view, obj: Anomaly) -> bool:
        if view.action == "fix":
            return self.user_has_permission("fix", request.user, obj)
        return False

    @staticmethod
    def user_has_permission(action: str, user: User, anomaly: Anomaly = None) -> bool:
        if action == "fix":
            if not user.is_authenticated:
                return False
            # user must be an admin in the project
            # or instructor in the collection's library
            return UserRole.objects.filter(
                Q(
                    user=user,
                    role=Role.PROJECT_ADMIN,
                    project=anomaly.segment.collection.project,
                )
                | Q(
                    user=user,
                    role=Role.INSTRUCTOR,
                    project=anomaly.segment.collection.project,
                    library=anomaly.segment.collection.library,
                )
            ).exists()
        return False

    @staticmethod
    def user_can_create_anomaly(user: User, segment: Segment) -> bool:
        # Check if the user has permission to create an anomaly for the given segment.
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        # user must be a controller in the project
        # or instructor in the project for another library as the segment's collection library
        return UserRole.objects.filter(
            Q(
                user=user,
                role=Role.INSTRUCTOR,
                project=segment.collection.project,
                library__in=Subquery(
                    Library.objects.filter(
                        Q(project=segment.collection.project) & ~Q(id=segment.collection.library_id)
                    ).values("id")
                ),
            )
            | Q(user=user, role=Role.CONTROLLER, project=segment.collection.project)
        ).exists()
