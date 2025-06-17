from django.db.models import Prefetch
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from epl.apps.project.models import Project, Role, UserRole
from epl.apps.project.serializers.project import (
    AssignRoleSerializer,
    ProjectInvitationsSerializer,
    ProjectSerializer,
    ProjectUserSerializer,
    UserRoleSerializer,
)
from epl.apps.user.models import User
from epl.libs.pagination import PageNumberPagination
from epl.schema_serializers import UnauthorizedSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["project"],
        summary=_("List all projects"),
        responses={
            status.HTTP_200_OK: ProjectSerializer(many=True),
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
        },
        parameters=[
            OpenApiParameter(
                name="user_id",
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.UUID,
                description="Filter projects by user_id",
            )
        ],
    ),
    create=extend_schema(
        tags=["project"],
        summary=_("Create a new project"),
        responses={
            status.HTTP_201_CREATED: ProjectSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
        },
    ),
    retrieve=extend_schema(
        tags=["project"],
        summary=_("Retrieve project details"),
        responses={
            status.HTTP_200_OK: ProjectSerializer,
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    ),
    update=extend_schema(
        tags=["project"],
        summary=_("Update a project"),
        responses={
            status.HTTP_200_OK: ProjectSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    ),
    partial_update=extend_schema(
        tags=["project"],
        summary=_("Partially update a project"),
        responses={
            status.HTTP_200_OK: ProjectSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    ),
    destroy=extend_schema(
        tags=["project"],
        summary=_("Delete a project"),
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    ),
)
class ProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet to handle all project operations.
    """

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list" and self.request.user.is_authenticated and self.request.GET.get("user_id"):
            project_ids = UserRole.objects.filter(user=self.request.user).values_list("project_id", flat=True)
            return queryset.filter(id__in=project_ids)
        return queryset

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
    def users(self, request, pk=None):
        project = self.get_object()
        users = (
            User.objects.active()
            .filter(project_roles__project=project)
            .prefetch_related(Prefetch("project_roles", queryset=UserRole.objects.filter(project=project)))
            .distinct()
        )
        serializer = ProjectUserSerializer(users, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=["project", "user"],
        summary=_("Assign roles for a user in a project"),
        responses={
            status.HTTP_201_CREATED: AssignRoleSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
        request=AssignRoleSerializer,
    )
    @action(detail=True, methods=["post"], url_path="roles")
    def assign_roles(self, request, pk=None):
        project = self.get_object()

        serializer = AssignRoleSerializer(data=request.data, context={"project": project, "request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["project", "user"],
        summary=_("Remove roles for a user in a project"),
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
        request=AssignRoleSerializer,
    )
    @assign_roles.mapping.delete
    def remove_roles(self, request, pk=None):
        project = self.get_object()

        serializer = AssignRoleSerializer(data=request.query_params, context={"project": project, "request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["project", "user"],
        summary=_("List all roles"),
        responses={
            status.HTTP_200_OK: UserRoleSerializer(many=True),
        },
    )
    @action(detail=False, methods=["get"], url_path="roles", permission_classes=[AllowAny])
    def list_roles(self, request):
        """List all available roles"""
        roles = [{"role": role[0], "label": role[1]} for role in Role.choices]
        serializer = UserRoleSerializer(roles, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=["project"],
        summary=_("Update invitations for a project"),
        description=_(
            "Update the list of invitations for a project. "
            "The request body should be an object with an 'invitations' key containing a list of invitations."
        ),
        request=ProjectInvitationsSerializer,
        responses={
            status.HTTP_200_OK: ProjectSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    @action(detail=True, methods=["patch"], url_path="invitations")
    def update_invitations(self, request, pk=None):
        project = self.get_object()
        print("Request data for invitations:", request.data)
        serializer = ProjectInvitationsSerializer(data=request.data, context={"project": project})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProjectSerializer(project).data, status=status.HTTP_200_OK)
