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
        status = int(request.query_params.get(self.status_param, 0))
        if status not in ResourceStatus:
            raise ValidationError({"status": _("Invalid status value")})

        if project_id := request.query_params.get(self.project_param, None):
            try:
                _project = Project.objects.filter(id=project_id).exists()
                queryset = queryset.filter(project_id=project_id)
            except (Project.DoesNotExist, DjangoValidationError):
                raise ValidationError({"project": _("Project not found")})

        if library_id := request.query_params.get(self.library_param, None):
            try:
                _library = Library.objects.filter(id=library_id).exists()
            except (Library.DoesNotExist, DjangoValidationError):
                raise ValidationError({"library": _("Library not found")})

            # Only return resources that must be instructed by the specified library
            if status == ResourceStatus.INSTRUCTION_BOUND:
                queryset = queryset.filter(instruction_turns__bound_copies__turns__0=str(library_id))
            if status == ResourceStatus.INSTRUCTION_UNBOUND:
                queryset = queryset.filter(instruction_turns__unbound_copies__turns__0=str(library_id))

        if status == ResourceStatus.POSITIONING:
            # If a Resource is in Instruction or Control positioning status but does
            # not have any segments assigned yet, we consider it can still be positioned.
            queryset = queryset.filter(
                Q(status=ResourceStatus.POSITIONING) | Q(collections__segments__isnull=True)
            ).distinct()
        elif status > ResourceStatus.POSITIONING:
            queryset = queryset.filter(status=status)

        if against_id := request.query_params.get(self.against_param, None):
            try:
                _against_library = Library.objects.filter(id=against_id).exists()
            except (Library.DoesNotExist, DjangoValidationError):
                raise ValidationError({"against": _("Library to compare against not found")})

        if against_id and library_id:
            if against_id == library_id:
                raise ValidationError(
                    {"against": _("The library to compare against cannot be the same as the current library")}
                )
            else:
                queryset = queryset.filter(
                    Q(collections__library_id=against_id) | Q(collections__library_id=library_id)
                )
        elif library_id and not against_id:
            queryset = queryset.filter(collections__library_id=library_id)
        elif against_id and not library_id:
            raise ValidationError({"against": _("You must specify a library to compare against")})

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
                "required": False,
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
