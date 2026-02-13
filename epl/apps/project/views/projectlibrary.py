from uuid import UUID

from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from epl.apps.project.models import ProjectLibrary
from epl.apps.project.permissions.projectlibrary import ProjectLibraryPermissions
from epl.apps.project.serializers.projectlibrary import ProjectLibraryPatchSerializer
from epl.schema_serializers import UnauthorizedSerializer


class ProjectLibraryViewSet(
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [ProjectLibraryPermissions]
    serializer_class = ProjectLibraryPatchSerializer
    queryset = ProjectLibrary.objects.all()

    @extend_schema(
        tags=["project"],
        summary=_("Specify if the library is an alternative storage location"),
        request=ProjectLibraryPatchSerializer,
        parameters=[
            OpenApiParameter(
                name="pk",
                description="The UUID of the library.",
                required=True,
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.UUID,
            ),
            OpenApiParameter(
                name="project_pk",
                description="The UUID of the project to which the library belongs.",
                required=True,
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.UUID,
            ),
        ],
        responses={
            status.HTTP_200_OK: ProjectLibraryPatchSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    def partial_update(self, request, project_pk: UUID = None, pk=None):
        project_library = get_object_or_404(ProjectLibrary.objects.all(), project_id=project_pk, library_id=pk)
        self.check_object_permissions(self.request, project_library)
        project_library.is_alternative_storage_site = bool(request.data.get("is_alternative_storage_site"))
        project_library.save(update_fields=["is_alternative_storage_site"])
        return Response(
            {"is_alternative_storage_site": project_library.is_alternative_storage_site}, status=status.HTTP_200_OK
        )
