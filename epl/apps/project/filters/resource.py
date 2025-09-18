from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from rest_framework import filters
from rest_framework.exceptions import ValidationError

from epl.apps.project.models import Library, Project, ResourceStatus


class ResourceFilter(filters.BaseFilterBackend):
    project_param = "project"
    project_param_description = _("Project ID to which the collection belongs")
    library_param = "library"
    library_param_description = _("Library ID to which the collection belongs")
    against_param = "against"
    against_param_description = _("ID of the library to compare against")
    status_param = "status"
    status_param_description = _("Filter by resource status")

    def filter_queryset(self, request, queryset, view):
        if view.action == "list":
            status = int(request.query_params.get(self.status_param, 0))
            if status not in ResourceStatus:
                raise ValidationError({"status": _("Invalid status value")})

            library = None
            if library_id := request.query_params.get(self.library_param, None):
                try:
                    library = Library.objects.get(id=library_id)
                except (Library.DoesNotExist, DjangoValidationError):
                    raise ValidationError({"library": _("Library not found")})

            against_library = None
            if against_id := request.query_params.get(self.against_param, None):
                try:
                    against_library = Library.objects.get(id=against_id)
                except (Library.DoesNotExist, DjangoValidationError):
                    raise ValidationError({"against": _("Library to compare against not found")})

            if project_id := request.query_params.get(self.project_param, None):
                try:
                    project = Project.objects.get(id=project_id)
                    queryset = queryset.filter(project=project)
                except (Project.DoesNotExist, DjangoValidationError):
                    raise ValidationError({"project": _("Project not found")})

            if not library:
                # Not for a specific library
                queryset = self.filter_no_library(queryset, status)
            else:
                # Resources having collections in the specified library
                # optionally in common with another library
                queryset = self.filter_for_library(queryset, status, library, against_library)

        return queryset

    def filter_for_library(self, queryset, status, library, against_library=None):
        if status == ResourceStatus.POSITIONING:
            # If a Resource is in Instruction or Control positioning status but does
            # not have any segments assigned yet, we consider it can still be positioned.
            queryset = queryset.filter(collections__library=library)

            queryset = queryset.filter(Q(status=status) | Q(collections__segments__isnull=True))

        elif status == ResourceStatus.INSTRUCTION_BOUND:
            queryset = queryset.filter(
                status=status,
                collections__library=library,
                instruction_turns__bound_copies__turns__0__library=str(library.id),
            )

        elif status == ResourceStatus.INSTRUCTION_UNBOUND:
            queryset = queryset.filter(
                status=status,
                collections__library=library,
                instruction_turns__unbound_copies__turns__0__library=str(library.id),
            )

        elif status in [ResourceStatus.CONTROL_BOUND, ResourceStatus.CONTROL_UNBOUND]:
            queryset = queryset.filter(status=status, collections__library=library)

        if against_library:
            queryset = queryset.filter(collections__library=against_library)

        return queryset

    def filter_no_library(self, queryset, status):
        if status == ResourceStatus.POSITIONING:
            # If a Resource is in Instruction or Control positioning status but does
            # not have any segments assigned yet, we consider it can still be positioned.
            queryset = queryset.filter(
                Q(status=ResourceStatus.POSITIONING) | Q(collections__segments__isnull=True)
            ).distinct()
        elif status > ResourceStatus.POSITIONING:
            queryset = queryset.filter(status=status)
        return queryset

    def get_schema_operation_parameters(self, view):
        return [
            {
                "name": self.project_param,
                "required": True,
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
            {
                "name": self.status_param,
                "required": True,
                "in": "query",
                "description": str(self.status_param_description),
                "schema": {
                    "type": "integer",
                    "enum": [
                        ResourceStatus.POSITIONING,
                        ResourceStatus.INSTRUCTION_BOUND,
                        ResourceStatus.CONTROL_BOUND,
                        ResourceStatus.INSTRUCTION_UNBOUND,
                        ResourceStatus.CONTROL_UNBOUND,
                    ],
                },
            },
        ]
