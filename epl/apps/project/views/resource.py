from django.contrib.postgres.aggregates import StringAgg
from django.db import models
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin, UpdateModelMixin
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from epl.apps.project.filters.resource import ResourceFilter
from epl.apps.project.models import Resource, ResourceStatus
from epl.apps.project.permissions.resource import ResourcePermission
from epl.apps.project.serializers.common import StatusListSerializer
from epl.apps.project.serializers.resource import ResourceSerializer, ResourceWithCollectionsSerializer
from epl.libs.pagination import PageNumberPagination


@extend_schema_view(
    list=extend_schema(
        tags=["collection", "resource"],
        responses={200: ResourceSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["collection", "resource"],
        responses={200: ResourceSerializer()},
    ),
    update=extend_schema(
        tags=["collection", "resource"],
        responses={200: ResourceSerializer()},
    ),
    partial_update=extend_schema(
        tags=["collection", "resource"],
        responses={200: ResourceSerializer()},
    ),
)
class ResourceViewSet(ListModelMixin, UpdateModelMixin, RetrieveModelMixin, GenericViewSet):
    queryset = Resource.objects.prefetch_related("collections").all()
    serializer_class = ResourceSerializer
    permission_classes = [ResourcePermission]
    pagination_class = PageNumberPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, ResourceFilter]
    search_fields = ["title", "=code"]
    ordering_fields = ["title", "count", "status"]

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.action == "list":
            queryset = queryset.annotate(
                count=models.Count("collections"),
                call_numbers=StringAgg(
                    "collections__call_number",
                    delimiter=", ",
                    filter=models.Q(collections__call_number__isnull=False) & ~models.Q(collections__call_number=""),
                    output_field=models.CharField(),
                ),
            )

        return queryset

    @extend_schema(
        tags=["collection", "resource"],
        request=None,
        responses={200: StatusListSerializer(many=True)},
        description="List all possible resource statuses.",
        summary="List Resource Statuses",
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="status",
        permission_classes=[AllowAny],
        pagination_class=None,
        filter_backends=[],
    )
    def list_statuses(self, request, pk=None):
        statuses = [{"status": _s[0], "label": _s[1]} for _s in ResourceStatus.choices]
        serializer = StatusListSerializer(statuses, many=True)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="project_id",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=True,
                description="ID du projet",
            )
        ],
        responses=ResourceWithCollectionsSerializer,
        tags=["collection", "resource"],
    )
    @action(detail=True, methods=["get"], url_path="collections")
    def collections(self, request, pk=None):
        project_id = request.query_params.get("project_id")
        if not project_id:
            return Response({"detail": "project_id is required"}, status=400)
        resource = self.get_object()
        collections = resource.collections.filter(project_id=project_id)
        serializer = ResourceWithCollectionsSerializer(
            {
                "resource": resource,
                "collections": collections,
            },
            context={"request": request, "view": self},
        )
        return Response(serializer.data)
