from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from epl.apps.project.models import Anomaly, Segment
from epl.apps.project.permissions.anomaly import AnomalyPermissions
from epl.apps.project.serializers.anomaly import AnomalySerializer
from epl.schema_serializers import UnauthorizedSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["anomaly", "instruction"],
        summary="List anomalies",
        description="List all anomalies",
        parameters=[
            OpenApiParameter(
                name="segment",
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.UUID,
                description=_("Filter by segment ID (one of segment, project or resource is required)"),
            ),
            OpenApiParameter(
                name="project",
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.UUID,
                description=_("Filter by project ID (one of segment, project or resource is required)"),
            ),
            OpenApiParameter(
                name="resource",
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.UUID,
                description=_("Filter by resource ID (one of segment, project or resource is required)"),
            ),
        ],
        responses={
            status.HTTP_200_OK: AnomalySerializer(many=True),
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
        },
    ),
    create=extend_schema(
        tags=["anomaly", "instruction"],
        summary="Create anomaly",
        description="Create a new anomaly",
        request=AnomalySerializer,
        responses={
            status.HTTP_201_CREATED: AnomalySerializer,
            status.HTTP_400_BAD_REQUEST: None,
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
        },
    ),
    destroy=extend_schema(
        tags=["anomaly", "instruction"],
        summary="Delete an anomaly",
        description="Delete an anomaly",
        request=None,
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_403_FORBIDDEN: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_404_NOT_FOUND: None,
        },
    ),
)
class AnomalyViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, GenericViewSet):
    queryset = Anomaly.objects.all().select_related("segment", "created_by", "fixed_by")
    serializer_class = AnomalySerializer
    permission_classes = [AnomalyPermissions]
    pagination_class = None

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)

        if self.action == "list":
            if project := self.request.query_params.get("project"):
                return queryset.filter(resource__project__id=project)
            if resource := self.request.query_params.get("resource"):
                return queryset.filter(resource__id=resource)
            if segment := self.request.query_params.get("segment"):
                return queryset.filter(segment__id=segment)

        return queryset

    def check_permissions(self, request):
        if self.action == "create":
            _segment = Segment.objects.get(pk=request.data.get("segment_id"))
            if not AnomalyPermissions.user_can_create_anomaly(request.user, _segment):
                self.permission_denied(
                    request,
                    message=_("You do not have permission to create an anomaly for this segment."),
                )
        return super().check_permissions(request)

    @extend_schema(
        tags=["anomaly", "instruction"],
        summary=_("Fix an anomaly"),
        description=_("Mark an anomaly as fixed"),
        request=None,
        responses={
            status.HTTP_200_OK: AnomalySerializer,
            status.HTTP_400_BAD_REQUEST: {"type": "object", "properties": {"detail": {"type": "string"}}},
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_404_NOT_FOUND: None,
        },
    )
    @action(detail=True, methods=["patch"], url_path="fix", permission_classes=[AnomalyPermissions])
    def fix(self, request, pk):
        anomaly = self.get_object()
        serializer = self.get_serializer(anomaly)
        serializer.fix()
        return Response(serializer.data)
