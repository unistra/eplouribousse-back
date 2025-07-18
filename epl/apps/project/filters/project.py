from django.utils.translation import gettext_lazy as _
from rest_framework import filters

from epl.apps.project.filters import QueryParamMixin


class ProjectFilter(QueryParamMixin, filters.BaseFilterBackend):
    status_param = "status"
    status_param_description = _("Filter projects by status")
    participating_param = "participant"
    participating_param_description = _("Filter projects the user has a role in")
    library_param = "library"
    library_param_description = _("Filter projects including a specific library")
    show_archived_param = "show_archived"
    show_archived_param_description = _("Include archived projects in the results")

    def filter_queryset(self, request, queryset, view):
        status = self.get_int(request, self.status_param, None)
        if status is not None:
            queryset = queryset.status(status)
        if self.get_bool(request, self.participating_param, False) and hasattr(request, "user"):
            queryset = queryset.participant(request.user)
        if library_id := self.get_uuid(request, self.library_param, None):
            queryset = queryset.filter(libraries__id=library_id)
        if self.get_bool(request, self.show_archived_param, False):
            # We explicitly don't exclude archived projects
            queryset = queryset.exclude_archived(exclude=False)
        else:
            # By default, archived projects are excluded
            queryset = queryset.exclude_archived(exclude=True)
        return queryset

    def get_schema_operation_parameters(self, view):
        return [
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
            {
                "name": self.show_archived_param,
                "required": False,
                "in": "query",
                "description": str(self.show_archived_param_description),
                "schema": {
                    "type": "boolean",
                    "default": False,
                },
            },
        ]
