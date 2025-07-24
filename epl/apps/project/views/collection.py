from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, mixins, parsers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from epl.apps.project.filters.collection import CollectionFilter
from epl.apps.project.models import Collection
from epl.apps.project.permissions.collection import CollectionPermission
from epl.apps.project.serializers.collection import (
    CollectionSerializer,
    ExclusionSerializer,
    ImportSerializer,
    PositioningCommentSerializer,
    PositionSerializer,
)
from epl.libs.pagination import PageNumberPagination
from epl.schema_serializers import UnauthorizedSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["collection", "project"],
        summary=_("List collections"),
        request=CollectionSerializer,
        responses={
            status.HTTP_200_OK: CollectionSerializer,
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
        },
    ),
    destroy=extend_schema(
        tags=["collection"],
        summary=_("Delete a collection"),
        description=_("Delete a collection permanently. This action requires project creator permissions."),
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_403_FORBIDDEN: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    ),
)
class CollectionViewSet(mixins.ListModelMixin, mixins.DestroyModelMixin, GenericViewSet):
    queryset = Collection.objects.select_related("resource").all()
    serializer_class = CollectionSerializer
    permission_classes = [CollectionPermission]
    pagination_class = PageNumberPagination
    filter_backends = [filters.SearchFilter, CollectionFilter]
    search_fields = ["title", "=code"]

    @extend_schema(
        tags=["collection"],
        summary="Import a collection",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "csv_file": {
                        "type": "string",
                        "format": "binary",
                        "description": "CSV file to import",
                    },
                    "library": {
                        "type": "string",
                        "format": "uuid",
                        "description": _("Library ID to which the collection belongs"),
                    },
                    "project": {
                        "type": "string",
                        "format": "uuid",
                        "description": _("Project ID to which the collection belongs"),
                    },
                },
                "required": ["csv_file", "library", "project"],
            }
        },
        responses={
            status.HTTP_200_OK: {
                "type": "object",
                "additionalProperties": {
                    "type": "integer",
                    "description": _(
                        "Key represents the number of duplicates (1=unique, 2=duplicate, 3=triplicate, etc), value is the count"
                    ),
                },
                "example": {"1": 10, "2": 3, "3": 2},
            },
            status.HTTP_400_BAD_REQUEST: {
                "type": "object",
                "properties": {"detail": {"type": "string"}},
            },
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
        },
    )
    @action(
        methods=["post"],
        detail=False,
        url_path="import-csv",
        url_name="import_csv",
        parser_classes=[parsers.MultiPartParser],
    )
    def import_csv(self, request):
        """
        Import collections for a library and a project from a CSV file.
        """
        self.check_object_permissions(request, None)
        serializer = ImportSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        imported_collections: dict[int, int] = serializer.save()
        return Response(imported_collections, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["collection"],
        summary="Position a collection",
        description="Set or update the position of a collection by providing its new rank.",
        request=PositionSerializer,
        responses=PositionSerializer,
    )
    @action(
        detail=True,
        methods=["patch"],
        url_path="position",
        url_name="position",
        serializer_class=PositionSerializer,
    )
    def position(self, request, pk=None):
        """
        Position a collection.
        """
        collection = self.get_object()
        serializer = self.get_serializer(collection, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(PositionSerializer(collection).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["collection"],
        summary="Exclude a collection",
        description="Exclude a collection by providing a valid exclusion reason.",
        request=ExclusionSerializer,
        responses=ExclusionSerializer,
    )
    @action(
        detail=True,
        methods=["patch"],
        url_path="exclude",
        serializer_class=ExclusionSerializer,
    )
    def exclude(self, request, pk=None):
        collection = self.get_object()
        serializer = self.get_serializer(collection, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ExclusionSerializer(collection).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["collection"],
        summary="Set or update the positioning comment",
        description="Set or update the instructor's comment on the collection positioning.",
        request=PositioningCommentSerializer,
        responses=PositioningCommentSerializer,
    )
    @action(
        detail=True,
        methods=["patch"],
        url_path="comment-positioning",
        serializer_class=PositioningCommentSerializer,
    )
    def comment_positioning(self, request, pk=None):
        collection = self.get_object()
        serializer = self.get_serializer(collection, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(PositioningCommentSerializer(collection).data, status=status.HTTP_200_OK)
