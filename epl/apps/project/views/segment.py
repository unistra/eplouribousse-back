from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import exceptions, status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin, DestroyModelMixin, ListModelMixin, UpdateModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from epl.apps.project.models import Resource, ResourceStatus, Segment
from epl.apps.project.models.choices import SegmentType
from epl.apps.project.permissions.segment import SegmentPermissions
from epl.apps.project.serializers.segment import SegmentOrderSerializer, SegmentSerializer
from epl.schema_serializers import UnauthorizedSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["segment"],
        summary=_("List segments"),
        description=_("List segments for a specific resource"),
        parameters=[
            OpenApiParameter(
                name="resource_id",
                location=OpenApiParameter.QUERY,
                required=True,
                type=OpenApiTypes.UUID,
                description=_("Collection ID to filter segments"),
            )
        ],
        responses={
            status.HTTP_200_OK: SegmentSerializer(many=True),
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
        },
    ),
    create=extend_schema(
        tags=["segment"],
        summary=_("Create a segment"),
        request=SegmentSerializer,
        responses={
            status.HTTP_201_CREATED: SegmentSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
        },
    ),
    partial_update=extend_schema(
        tags=["segment"],
        summary=_("Partially update a segment"),
        request=SegmentSerializer,
        responses={
            status.HTTP_200_OK: SegmentSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
        },
    ),
    destroy=extend_schema(
        tags=["segment"],
        summary=_("Delete a segment"),
        description=_("Delete a segment permanently"),
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    ),
)
class SegmentViewSet(ListModelMixin, CreateModelMixin, UpdateModelMixin, DestroyModelMixin, GenericViewSet):
    http_method_names = ["get", "post", "patch", "delete"]
    queryset = Segment.objects.all()
    permission_classes = [SegmentPermissions]
    serializer_class = SegmentSerializer
    pagination_class = None

    def get_segment_type(self, resource: Resource):
        return SegmentType.BOUND if resource.status <= ResourceStatus.INSTRUCTION_BOUND else SegmentType.UNBOUND

    def get_queryset(self):
        if self.action != "list":
            return super().get_queryset()

        resource_id = self.request.query_params.get("resource_id")
        if not resource_id:
            raise exceptions.ValidationError({"detail": _("Missing required query parameter: resource_id")})
        try:
            resource = Resource.objects.get(id=resource_id)
            queryset = resource.segments
        except Resource.DoesNotExist:
            raise exceptions.NotFound({"detail": _("Resource does not exist")})
        return queryset.order_by("order")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        collection = instance.collection

        instance.delete()

        segments_to_update = Segment.objects.filter(collection=collection).order_by("order")

        for index, segment in enumerate(segments_to_update):
            new_order = index + 1
            if segment.order != new_order:
                segment.order = new_order
                segment.save(update_fields=["order"])

    @extend_schema(
        tags=["segment"],
        summary=_("Move segment up"),
        description=_("Move the selected segment up in the order, and move the previous down"),
        request=None,
        responses={
            status.HTTP_200_OK: SegmentOrderSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    @action(detail=True, methods=["patch"], url_path="up")
    def up(self, request, pk=None):
        segment = self.get_object()

        serializer = SegmentOrderSerializer()
        result = serializer.move_up(segment)
        return Response(serializer.to_representation(result), status=status.HTTP_200_OK)

    @extend_schema(
        tags=["segment"],
        summary=_("Move segment down"),
        description=_("Move the selected segment down in the order, and move the next up"),
        request=None,
        responses={
            status.HTTP_200_OK: SegmentOrderSerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
    )
    @action(detail=True, methods=["patch"], url_path="down")
    def down(self, request, pk=None):
        segment = self.get_object()

        serializer = SegmentOrderSerializer()
        result = serializer.move_down(segment)
        return Response(serializer.to_representation(result), status=status.HTTP_200_OK)
