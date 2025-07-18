from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from epl.apps.project.models import ProjectLibrary
from epl.schema_serializers import UnauthorizedSerializer

project_library_patch_inline_serializer = inline_serializer(
    "ProjectLibraryPatchSerializer", fields={"is_alternative_storage_site": serializers.BooleanField()}
)


class ProjectLibraryViewSet(viewsets.ModelViewSet):
    @extend_schema(
        tags=["project"],
        summary=_("Specify if the library is an alternative storage location"),
        request=project_library_patch_inline_serializer,
        responses={
            status.HTTP_200_OK: project_library_patch_inline_serializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    def partial_update(self, request, project_pk=None, pk=None):
        project_library = get_object_or_404(ProjectLibrary.objects.all(), project_id=project_pk, library_id=pk)
        project_library.is_alternative_storage_site = bool(request.data.get("is_alternative_storage_site"))
        project_library.save(update_fields=["is_alternative_storage_site"])
        return Response(
            {"is_alternative_storage_site": project_library.is_alternative_storage_site}, status=status.HTTP_200_OK
        )
