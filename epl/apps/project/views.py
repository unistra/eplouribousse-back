from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from epl.apps.project.models import Project, UserRole
from epl.apps.project.serializers import ProjectSerializer, ProjectUserSerializer
from epl.apps.user.models import User
from epl.schema_serializers import UnauthorizedSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet to handle all project operations.
    """

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["project"],
        summary=_("List all projects"),
        responses={
            status.HTTP_200_OK: ProjectSerializer(many=True),
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
        },
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=["project"],
        summary=_("Create a new project"),
        responses={
            status.HTTP_201_CREATED: ProjectSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
        },
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=["project"],
        summary=_("Retrieve project details"),
        responses={
            status.HTTP_200_OK: ProjectSerializer,
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=["project"],
        summary=_("Update a project"),
        responses={
            status.HTTP_200_OK: ProjectSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=["project"],
        summary=_("Partially update a project"),
        responses={
            status.HTTP_200_OK: ProjectSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=["project"],
        summary=_("Delete a project"),
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=["project"],
        summary=_("List projects for a user"),
        parameters=[
            OpenApiParameter(
                name="user_id",
                description=_(
                    "User ID to get projects for. If not provided, returns projects for the authenticated user."
                ),
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
    @action(detail=False, methods=["get"], url_path="user-projects")
    def user_projects(self, request):
        user_id = request.query_params.get("user_id")

        if user_id:
            user = get_object_or_404(User, id=user_id)
        else:
            user = request.user

        user_roles = UserRole.objects.filter(user=user)
        project_ids = user_roles.values_list("project_id", flat=True)
        projects = Project.objects.filter(id__in=project_ids).distinct()

        serializer = self.get_serializer(projects, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=["project"],
        summary=_("List users associated with a project"),
        responses={
            status.HTTP_200_OK: ProjectUserSerializer(many=True),
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    @action(detail=True, methods=["get"], url_path="users")
    def project_users(self, request, pk=None):
        """
        Get all users who have roles in this project.
        """
        project = self.get_object()
        users_data = ProjectUserSerializer.get_users_with_roles_for_project(project)
        return Response(users_data)
