from django.contrib.postgres.aggregates import StringAgg
from django.db import models
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import filters
from rest_framework.exceptions import ValidationError
from rest_framework.viewsets import ModelViewSet

from epl.apps.project.models import Library, Project, Resource
from epl.apps.project.permissions.resource import ResourcePermission
from epl.apps.project.serializers.resource import ResourceSerializer
from epl.libs.pagination import PageNumberPagination


@extend_schema_view(
    list=extend_schema(
        tags=["collection", "resource"],
        parameters=[
            OpenApiParameter(
                name="library",
                required=False,
                location=OpenApiParameter.QUERY,
                description=_("Library ID to which the resource belongs"),
                type=OpenApiTypes.UUID,
                pattern="^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            ),
            OpenApiParameter(
                name="project",
                required=True,
                location=OpenApiParameter.QUERY,
                description=_("Project ID to which the resource belongs"),
                type=OpenApiTypes.UUID,
                pattern="^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            ),
        ],
    ),
)
class ResourceViewSet(ModelViewSet):
    queryset = Resource.objects.prefetch_related("collections").all()
    serializer_class = ResourceSerializer
    permission_classes = [ResourcePermission]
    pagination_class = PageNumberPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ["title", "=code"]

    def get_queryset(self):
        library_id = self.request.query_params.get("library", None)
        project_id = self.request.query_params.get("project", None)

        queryset = self.queryset

        if project_id is not None:
            try:
                project = Project.objects.all().get(pk=project_id)
                queryset = queryset.filter(project=project)
            except Project.DoesNotExist:
                raise ValidationError(_("Project not found"))
        if library_id is not None:
            try:
                library = Library.objects.get(pk=library_id)
                queryset = queryset.filter(collections__library=library)
            except Library.DoesNotExist:
                raise ValidationError(_("Library not found"))

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
