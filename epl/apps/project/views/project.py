from django.db.models import Prefetch
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from epl.apps.project.models import Project, Role, Status, UserRole
from epl.apps.project.permissions.project import ProjectStatusPermissions
from epl.apps.project.serializers.project import (
    AssignRoleSerializer,
    InvitationSerializer,
    ProjectDetailSerializer,
    ProjectLibrarySerializer,
    ProjectSerializer,
    ProjectUserSerializer,
    SetStatusSerializer,
    StatusListSerializer,
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
    create=extend_schema(  # Swagger doesn't let me send the request when under format application/x-www-form-urlencoded ??
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

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProjectDetailSerializer
        return super().get_serializer_class()

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
        tags=["project"],
        summary=_("Update the status of a project"),
        request=SetStatusSerializer,
        responses={
            status.HTTP_200_OK: SetStatusSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    @action(detail=True, methods=["patch"], url_path="status", permission_classes=[ProjectStatusPermissions])
    def update_status(self, request, pk=None):
        """
        Change the status of a project.
        """
        project = self.get_object()
        serializer = SetStatusSerializer(instance=project, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["project"],
        summary=_("List all project statuses"),
        request=None,
        responses={
            status.HTTP_200_OK: StatusListSerializer(many=True),
        },
    )
    @action(detail=False, methods=["get"], url_path="status", permission_classes=[AllowAny], pagination_class=None)
    def list_statuses(self, request, pk=None):
        """
        List all available project statuses.
        """
        statuses = [{"status": _s[0], "label": _s[1]} for _s in Status.choices]
        serializer = StatusListSerializer(statuses, many=True)
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
        request=AssignRoleSerializer,
        parameters=[AssignRoleSerializer],
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
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
        summary="Add an invitation to the list of invitations, that will be fired at the end of the project creation",
        description="The invitation given will not be sent immediately. It should contain the email of the user to invite and the role they will have in the project, and the library_id if they're assigned to the role 'instructor'",
        request=InvitationSerializer,
        responses={
            status.HTTP_201_CREATED: ProjectDetailSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    @action(detail=True, methods=["post"], url_path="invitations")
    def add_invitation(self, request, pk=None):
        project = self.get_object()
        serializer = InvitationSerializer(data=request.data, context={"project": project, "request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProjectDetailSerializer(project).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["project"],
        summary="Remove a specific invitation from the list of invitations",
        description="The invitation, given as parameters in the request, will be removed from the list of invitations. Be careful, every field might be used to identify the invitation, so if you want to remove an invitation for a specific user, you should provide the email, the role and the library_id if the role is 'instructor'",
        request=InvitationSerializer,
        responses={
            status.HTTP_200_OK: ProjectDetailSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
        parameters=[InvitationSerializer],
    )
    @add_invitation.mapping.delete
    def remove_invitation(self, request, pk=None):
        project = self.get_object()
        serializer = InvitationSerializer(data=request.query_params, context={"project": project, "request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProjectDetailSerializer(project).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["project"],
        summary="Clear all invitations for a project",
        responses={
            status.HTTP_200_OK: ProjectDetailSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    @action(detail=True, methods=["delete"], url_path="invitations/clear")
    def clear_invitations(self, request, pk=None):
        project = self.get_object()
        serializer = InvitationSerializer(context={"project": project})
        serializer.clear()
        return Response(ProjectDetailSerializer(project).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["project"],
        summary="Assign a library to the project",
        description="Allows you to link a library to the project. The library must be created before adding it to the project",
        request=ProjectLibrarySerializer,
        responses={
            status.HTTP_200_OK: ProjectDetailSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    @action(detail=True, methods=["post"], url_path="libraries")
    def add_library(self, request, pk=None):
        project = self.get_object()
        serializer = ProjectLibrarySerializer(data=request.data, context={"project": project, "request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProjectDetailSerializer(project).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["project"],
        summary="Unassign a library to the project",
        description="Allows you to remove a library to the project",
        request=ProjectLibrarySerializer,
        parameters=[ProjectLibrarySerializer],
        responses={
            status.HTTP_200_OK: ProjectDetailSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    @add_library.mapping.delete
    def remove_library(self, request, pk=None):
        project = self.get_object()
        serializer = ProjectLibrarySerializer(
            data=request.query_params, context={"project": project, "request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProjectDetailSerializer(project).data, status=status.HTTP_200_OK)
