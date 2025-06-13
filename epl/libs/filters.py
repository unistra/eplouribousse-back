from django.utils.translation import gettext_lazy as _
from rest_framework import filters


class ExcludeFilter(filters.BaseFilterBackend):
    """
    Filter that excludes records with specific IDs.
    """

    exclude_param = "exclude"
    exclude_title = _("Exclude IDs")
    exclude_description = _("List of IDs to exclude.")

    def filter_queryset(self, request, queryset, view):
        exclude = request.query_params.getlist(self.exclude_param, None)
        if exclude:
            queryset = queryset.exclude(id__in=exclude)

        return queryset

    def get_schema_operation_parameters(self, view):
        return [
            {
                "name": self.exclude_param,
                "required": False,
                "in": "query",
                "description": str(self.exclude_description),
                "schema": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
            },
        ]
