from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from epl.apps.project.models import Project
from epl.apps.project.serializers import ProjectSerializer
from epl.apps.user.models import User, UserRole
from epl.schema_serializers import UnauthorizedSerializer


@extend_schema(
    tags=["project"],
    summary=_("List projects for a user"),
    parameters=[
        OpenApiParameter(
            name="user_id",
            description=_("User ID to get projects for. If not provided, returns projects for the authenticated user."),
            required=False,
            type=str,
        ),
    ],
    responses={
        status.HTTP_200_OK: ProjectSerializer(many=True),
        status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
        status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_projects(request: Request) -> Response:
    """
    Get projects for a user.
    If user_id is provided, returns projects for that user.
    Otherwise, returns projects for the authenticated user.
    """
    user_id = request.query_params.get("user_id")

    if user_id:
        user = get_object_or_404(User, id=user_id)
    else:
        user = request.user

    # Get projects where the user has a role
    user_roles = UserRole.objects.filter(user=user)
    project_ids = user_roles.values_list("project_id", flat=True)
    projects = Project.objects.filter(id__in=project_ids).distinct()

    serializer = ProjectSerializer(projects, many=True)
    return Response(serializer.data)
