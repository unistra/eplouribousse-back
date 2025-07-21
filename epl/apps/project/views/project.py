from django.db.models import Prefetch
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from epl.apps.project.filters.project import ProjectFilter
from epl.apps.project.models import Project, ProjectStatus, Role, UserRole
from epl.apps.project.permissions.project import ProjectPermissions
from epl.apps.project.serializers.project import (
    AssignRoleSerializer,
    ChangeStatusSerializer,
    CreateProjectSerializer,
    ExclusionReasonSerializer,
    InvitationSerializer,
    ProjectDetailSerializer,
    ProjectLibrarySerializer,
    ProjectSerializer,
    ProjectUserSerializer,
    StatusListSerializer,
    UserRoleSerializer,
)
from epl.apps.user.models import User
from epl.libs.pagination import PageNumberPagination
from epl.schema_serializers import UnauthorizedSerializer


@extend_schema_view(
    create=extend_schema(  # Swagger doesn't let me send the request when under format application/x-www-form-urlencoded ??
        tags=["project"],
        summary=_("Create a new project"),
        request=CreateProjectSerializer,
        responses={
            status.HTTP_201_CREATED: CreateProjectSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
        },
    ),
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
    retrieve=extend_schema(
        tags=["project"],
        summary=_("Retrieve project details"),
        responses={
            status.HTTP_200_OK: ProjectDetailSerializer,
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
    permission_classes = [ProjectPermissions]
    pagination_class = PageNumberPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, ProjectFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "is_private", "active_after", "status"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            queryset = Project.objects.public_or_participant(user=self.request.user)
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProjectDetailSerializer
        if self.action == "create":
            return CreateProjectSerializer
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
        request=ChangeStatusSerializer,
        responses={
            status.HTTP_200_OK: ChangeStatusSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    @action(detail=True, methods=["patch"], url_path="status")
    def update_status(self, request, pk=None):
        """
        Change the status of a project.
        """
        project = self.get_object()
        serializer = ChangeStatusSerializer(
            instance=project, data=request.data, partial=True, context={"request": request}
        )
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
        statuses = [{"status": _s[0], "label": _s[1]} for _s in ProjectStatus.choices]
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
            status.HTTP_201_CREATED: InvitationSerializer,
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
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["project"],
        summary="Remove a specific invitation from the list of invitations",
        description="The invitation, given as parameters in the request, will be removed from the list of invitations. Be careful, every field might be used to identify the invitation, so if you want to remove an invitation for a specific user, you should provide the email, the role and the library_id if the role is 'instructor'",
        request=InvitationSerializer,
        responses={
            status.HTTP_204_NO_CONTENT: None,
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
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["project"],
        summary="Clear all invitations for a project",
        responses={
            status.HTTP_204_NO_CONTENT: None,
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
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["project"],
        summary="Assign a library to the project",
        description="Allows you to link a library to the project. The library must be created before adding it to the project",
        request=ProjectLibrarySerializer,
        responses={
            status.HTTP_200_OK: ProjectLibrarySerializer,
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
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["project"],
        summary="Add an exclusion reason for collections in the project settings.",
        description="Allows you to add an exclusion reason for collections in the project settings. This exclusion reason will be added to the default ones.",
        request=ExclusionReasonSerializer,
        responses={
            status.HTTP_201_CREATED: ExclusionReasonSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    @action(detail=True, methods=["post"], url_path="exclusion_reason")
    def exclusion_reason(self, request, pk=None):
        project = self.get_object()
        serializer = ExclusionReasonSerializer(data=request.data, context={"project": project, "request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["project"],
        summary="Remove an exclusion reason for collections in the project settings.",
        description="Allows you to to remove an exclusion reason for collections in the project settings. This exclusion reason will be removed from the existing ones.",
        request=ExclusionReasonSerializer,
        parameters=[
            OpenApiParameter(
                name="exclusion_reason",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="The exclusion reason that should be removed.",
                required=True,
            )
        ],
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    @exclusion_reason.mapping.delete
    def remove_exclusion_reason(self, request, pk=None):
        project = self.get_object()
        serializer = ExclusionReasonSerializer(
            data=request.query_params, context={"project": project, "request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
