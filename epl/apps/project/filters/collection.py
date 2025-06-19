from django.utils.translation import gettext_lazy as _
from rest_framework import filters


class CollectionFilter(filters.BaseFilterBackend):
    """
    Filter to exclude collections based on a list of IDs.
    """

    project_param = "project"
    project_param_description = _("Project ID to which the collection belongs")
    library_param = "library"
    library_param_description = _("Library ID to which the collection belongs")
    against_param = "against"
    against_param_description = _("ID of the library to compare against")

    def filter_queryset(self, request, queryset, view):
        if project_id := request.query_params.get(self.project_param, None):
            queryset = queryset.filter(project_id=project_id)
        if library_id := request.query_params.get(self.library_param, None):
            queryset = queryset.filter(library_id=library_id)
        return queryset

    def get_schema_operation_parameters(self, view):
        return [
            {
                "name": self.project_param,
                "required": False,
                "in": "query",
                "description": str(self.project_param_description),
                "schema": {
                    "type": "string",
                    "format": "uuid",
                    "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                },
            },
            {
                "name": self.library_param,
                "required": False,
                "in": "query",
                "description": str(self.library_param_description),
                "schema": {
                    "type": "string",
                    "format": "uuid",
                    "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                },
            },
            {
                "name": self.against_param,
                "required": False,
                "in": "query",
                "description": str(self.against_param_description),
                "schema": {
                    "type": "string",
                    "format": "uuid",
                    "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                },
            },
        ]
