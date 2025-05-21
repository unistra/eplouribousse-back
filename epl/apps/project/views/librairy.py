from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated

from epl.apps.project.models.library import Library
from epl.apps.project.serializers.library import LibrairySerializer
from epl.libs.pagination import PageNumberPagination
from epl.schema_serializers import UnauthorizedSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["library"],
        summary=_("List all libraries"),
        responses={
            status.HTTP_200_OK: LibrairySerializer(many=True),
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
        },
    ),
    create=extend_schema(
        tags=["library"],
        summary=_("Create a new library"),
        responses={
            status.HTTP_201_CREATED: LibrairySerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
        },
    ),
    retrieve=extend_schema(
        tags=["library"],
        summary=_("Retrieve library details"),
        responses={
            status.HTTP_200_OK: LibrairySerializer,
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    ),
    update=extend_schema(
        tags=["library"],
        summary=_("Update a library"),
        responses={
            status.HTTP_200_OK: LibrairySerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    ),
    partial_update=extend_schema(
        tags=["library"],
        summary=_("Partially update a library"),
        responses={
            status.HTTP_200_OK: LibrairySerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    ),
    destroy=extend_schema(
        tags=["library"],
        summary=_("Delete a library"),
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    ),
)
class LibraryViewset(viewsets.ModelViewSet):
    """
    ViewSet to handle all Library operations.
    """

    queryset = Library.objects.all()
    serializer_class = LibrairySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination
