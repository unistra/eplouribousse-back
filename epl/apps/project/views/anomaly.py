from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.viewsets import ModelViewSet

from epl.apps.project.models import Anomaly
from epl.apps.project.permissions.anomaly import AnomalyPermissions
from epl.apps.project.serializers.anomaly import AnomalySerializer
from epl.libs.pagination import PageNumberPagination
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
                description=_("Filter by resource ID (one of segment, project or resource is required"),
            ),
        ],
        responses={
            status.HTTP_200_OK: AnomalySerializer(many=True),
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
        },
    )
)
class AnomalyViewSet(ModelViewSet):
    queryset = Anomaly.objects.all()
    serializer_class = AnomalySerializer
    permission_classes = [AnomalyPermissions]
    pagination_class = PageNumberPagination

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
