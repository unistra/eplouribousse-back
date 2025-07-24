from django.contrib.postgres.aggregates import StringAgg
from django.db import models
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin, UpdateModelMixin
from rest_framework.viewsets import GenericViewSet

from epl.apps.project.filters.resource import ResourceFilter
from epl.apps.project.models import Resource
from epl.apps.project.permissions.resource import ResourcePermission
from epl.apps.project.serializers.resource import ResourceSerializer
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
    filter_backends = [filters.SearchFilter, ResourceFilter]
    search_fields = ["title", "=code"]

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
