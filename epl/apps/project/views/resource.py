from django.contrib.postgres.aggregates import StringAgg
from django.db import models
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin, UpdateModelMixin
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from epl.apps.project.filters.resource import ResourceFilter
from epl.apps.project.models import Resource, ResourceStatus
from epl.apps.project.permissions.resource import ResourcePermission
from epl.apps.project.serializers.common import StatusListSerializer
from epl.apps.project.serializers.resource import (
    ResourceSerializer,
    ResourceWithCollectionsSerializer,
    ValidateControlSerializer,
)
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

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == "list":
            context.update({"library": self.request.query_params.get("library")})

        return context

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.action == "list":
            # Annotate with count of collections and aggregated call numbers within the specified project
            project = self.request.query_params.get("project")
            queryset = queryset.annotate(
                count=models.Count(
                    "collections",
                    filter=models.Q(collections__resource__project=project),
                    distinct=True,
                ),
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
        summary="Retrieve collections for a specific resource",
        description="Returns all collections associated with a specific resource within the same project. ",
        responses=ResourceWithCollectionsSerializer,
        tags=["collection", "resource"],
    )
    @action(detail=True, methods=["get"], url_path="collections")
    def collections(self, request, pk=None):
        resource = self.get_object()
        collections = resource.collections.annotate(
            fixed_anomalies=models.Count(
                "segments__anomalies",
                filter=models.Q(
                    segments__anomalies__fixed=True,
                ),
            ),
            unfixed_anomalies=models.Count(
                "segments__anomalies",
                filter=models.Q(
                    segments__anomalies__fixed=False,
                ),
            ),
        ).all()
        serializer = ResourceWithCollectionsSerializer(
            {
                "resource": resource,
                "collections": collections,
            },
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    @extend_schema(
        summary=_("Controller validates the instruction of the resource"),
        request=ValidateControlSerializer(),
        responses={
            status.HTTP_200_OK: ValidateControlSerializer(),
        },
        tags=["instruction", "resource"],
    )
    @action(detail=True, methods=["post"], url_path="control")
    def validate_control(self, request, pk=None):
        """
        Controller validates the current instruction phase (bound copies or unbound copies)
        for the resource
        """
        resource = self.get_object()
        serializer = ValidateControlSerializer(resource, data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
