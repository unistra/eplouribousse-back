from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
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
        summary=_("Bulk delete collections by library and project"),
        description=_(
            "Delete multiple collections belonging to a specific library within a specific project. Collections of the same library in other projects are not affected."
        ),
        parameters=[
            OpenApiParameter(
                name="library_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description=_("Library ID whose collections should be deleted"),
                required=True,
            ),
            OpenApiParameter(
                name="project_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description=_("Project ID to scope the deletion to"),
                required=True,
            ),
        ],
        responses={
            status.HTTP_200_OK: {
                "type": "object",
                "properties": {
                    "deleted_count": {"type": "integer", "description": _("Number of collections deleted")},
                    "message": {"type": "string", "description": _("Success message")},
                },
                "example": {"deleted_count": 15, "message": "Collections successfully deleted for library in project"},
            },
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_403_FORBIDDEN: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    @action(
        detail=False,
        methods=["delete"],
        url_path="bulk-delete",
        url_name="bulk_delete",
    )
    def bulk_delete(self, request):
        """
        Delete all collections of a specific library.
        Used to delete collections imported from a CSV file, during the project creation step.
        Collections from this library in other projects will not be deleted.
        """
        library_id = request.query_params.get("library_id")
        project_id = request.query_params.get("project_id")

        if not library_id:
            return Response({"detail": _("library_id parameter is required")}, status=status.HTTP_400_BAD_REQUEST)

        if not project_id:
            return Response({"detail": _("project_id parameter is required")}, status=status.HTTP_400_BAD_REQUEST)

        self.check_object_permissions(request, None)

        collections_to_delete = Collection.objects.filter(project_id=project_id, library_id=library_id)
        deleted_count = collections_to_delete.count()
        if deleted_count == 0:
            return Response(
                {"deleted_count": 0, "message": _("No collections found for this library in this project")},
                status=status.HTTP_200_OK,
            )

        collections_to_delete.delete()

        return Response(
            {"deleted_count": deleted_count, "message": _("Collections successfully deleted for library in project")},
            status=status.HTTP_200_OK,
        )

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
        summary="Add or update a comment on collection positioning",
        description="This comment is used to provide additional context on the collection's position.",
        request=PositioningCommentSerializer,
        responses=PositioningCommentSerializer,
    )
    @action(
        detail=True,
        methods=["post", "patch", "get"],
        url_path="comment-positioning",
        serializer_class=PositioningCommentSerializer,
    )
    def comment_positioning(self, request, pk=None):
        """
        We handle the positioning comment for a collection, using a generic relation to the Comment model.
        We do not create a separate viewset for this, because it is tightly coupled with the Collection model.
        At this point, the code only allows to manipulate the last comment with the subject "Positioning comment",
        but it should be sufficient for the use case defined in the user story.
        """
        collection = self.get_object()
        if request.method == "GET":
            comment = collection.comments.filter(subject=_("Positioning comment")).order_by("-created_at").first()
            if not comment:
                return Response({}, status=status.HTTP_404_NOT_FOUND)
            serializer = PositioningCommentSerializer(comment)
            return Response(serializer.data)
        elif request.method in ["POST", "PATCH"]:
            # Pour POST, on crée. Pour PATCH, on modifie le dernier commentaire.
            comment = None
            if request.method == "PATCH":
                comment = collection.comments.filter(subject=_("Positioning comment")).order_by("-created_at").first()
            serializer = PositioningCommentSerializer(
                comment, data=request.data, context={"request": request}, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(content_object=collection)
            return Response(
                serializer.data, status=status.HTTP_201_CREATED if request.method == "POST" else status.HTTP_200_OK
            )
