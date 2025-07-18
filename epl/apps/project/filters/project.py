from django.utils.translation import gettext_lazy as _
from rest_framework import filters

from epl.apps.project.filters import QueryParamMixin


class ProjectFilter(QueryParamMixin, filters.BaseFilterBackend):
    archived_param = "archived"
    archived_param_description = _("Whether to include archived projects")
    status_param = "status"
    status_param_description = _("Filter projects by status")
    private_param = "private"
    private_param_description = _("Whether to include private projects")
    participating_param = "participant"
    participating_param_description = _("Filter projects the user has a role in")
    library_param = "library"
    library_param_description = _("Filter projects including a specific library")

    def filter_queryset(self, request, queryset, view):
        if self.get_bool(request, self.archived_param, False):
            queryset = queryset.archived()
        if status := self.get_int(request, self.status_param, None) is not None:
            queryset = queryset.status(status)
        if self.get_bool(request, self.private_param, False):
            queryset = queryset.private()
        if self.get_bool(request, self.participating_param, False) and hasattr(request, "user"):
            queryset = queryset.participant(request.user)
        if library_id := self.get_uuid(request, self.library_param, None):
            queryset = queryset.filter(projectlibrary_set__id=library_id)
        return queryset

    def get_schema_operation_parameters(self, view):
        return [
            {
                "name": self.archived_param,
                "required": False,
                "in": "query",
                "description": str(self.archived_param_description),
                "schema": {
                    "type": "boolean",
                },
            },
            {
                "name": self.status_param,
                "required": False,
                "in": "query",
                "description": str(self.status_param_description),
                "schema": {
                    "type": "integer",
                },
            },
            {
                "name": self.private_param,
                "required": False,
                "in": "query",
                "description": str(self.private_param_description),
                "schema": {
                    "type": "boolean",
                },
            },
            {
                "name": self.participating_param,
                "required": False,
                "in": "query",
                "description": str(self.participating_param_description),
                "schema": {
                    "type": "boolean",
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
                    "pattern": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                },
            },
        ]
