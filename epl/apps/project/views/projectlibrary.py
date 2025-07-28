from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.response import Response

from epl.apps.project.models import ProjectLibrary
from epl.apps.project.permissions.projectlibrary import ProjectLibraryPermissions
from epl.apps.project.serializers.projectlibrary import ProjectLibraryAlternativeStorageSerializer
from epl.schema_serializers import UnauthorizedSerializer


class ProjectLibraryViewSet(viewsets.ModelViewSet):
    http_method_names = ["patch"]
    permission_classes = [ProjectLibraryPermissions]
    serializer_class = ProjectLibraryAlternativeStorageSerializer

    def get_object(self):
        """
        Find ProjectLibrary by project_id and library_id
        (from URL /projects/{project_pk}/libraries/{pk})
        """
        library_pk = self.kwargs.get("pk")
        project_pk = self.kwargs.get("project_pk")

        obj = ProjectLibrary.objects.get(project_id=project_pk, library_id=library_pk)
        self.check_object_permissions(self.request, obj)
        return obj

    @extend_schema(
        tags=["project"],
        summary=_("Specify if the library is an alternative storage location"),
        request=ProjectLibraryAlternativeStorageSerializer,
        responses={
            status.HTTP_200_OK: ProjectLibraryAlternativeStorageSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    def partial_update(self, request, project_pk=None, pk=None):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
