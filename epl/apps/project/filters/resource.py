from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Exists, IntegerChoices, OuterRef, Q
from django.utils.translation import gettext_lazy as _
from rest_framework import filters
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from epl.apps.project.filters import UUID_REGEX
from epl.apps.project.models import Library, Project, Resource, ResourceStatus
from epl.apps.project.models.collection import Arbitration


class PositioningFilter(IntegerChoices):
    ALL = 0, _("All")
    POSITIONING_ONLY = 10, _("Positioning only")
    INSTRUCTION_NOT_STARTED = 20, _("Instruction not started")
    # EXCLUDE_RESOURCES = 30, _("Exclude resources") Not yet


class ResourceFilter(filters.BaseFilterBackend):
    project_param = "project"
    project_param_description = _("Project ID to which the collection belongs")
    library_param = "library"
    library_param_description = _("Library ID to which the collection belongs")
    against_param = "against"
    against_param_description = _("ID of the library to compare against")
    status_param = "status[]"
    status_param_description = _("Filter by resource status")
    arbitration_param = "arbitration"
    arbitration_param_description = _("Filter by arbitration status")
    positioning_filter_param = "positioning_filter"
    positioning_filter_description = "Filter by positioning filter available"

    def filter_queryset(self, request, queryset, view):
        if view.action != "list":
            return queryset

        statuses = self._validate_status(request)
        library = self._get_library(request)
        against_library = self._get_against_library(request)

        queryset = self._apply_project_filter(request, queryset)
        queryset = self._apply_library_filter(queryset, statuses, library, against_library)
        queryset = self._apply_positioning_filter(request, queryset)
        queryset = self._apply_arbitration_filter(request, queryset)

        return queryset

    def _validate_status(self, request):
        statuses = request.query_params.getlist(self.status_param, ["0"])

        try:
            statuses = [int(v) for v in statuses]
        except (ValueError, TypeError):
            raise ValidationError({"status": _("Invalid status value")})

        for s in statuses:
            if s not in ResourceStatus:
                raise ValidationError({"status": _("Invalid status value")})
        return statuses

    @staticmethod
    def _get_library_param(request: Request, param_name: str, error_message) -> Library | None:
        library_id = request.query_params.get(param_name, None)
        if not library_id:
            return None
        try:
            return Library.objects.get(id=library_id)
        except (Library.DoesNotExist, DjangoValidationError):
            raise ValidationError({param_name: error_message})

    def _get_library(self, request) -> Library | None:
        return self._get_library_param(request, self.library_param, _("Library not found"))

    def _get_against_library(self, request) -> Library | None:
        return self._get_library_param(request, self.against_param, _("Library to compare against not found"))

    def _apply_project_filter(self, request, queryset):
        project_id = request.query_params.get(self.project_param, None)
        if not project_id:
            return queryset
        try:
            project = Project.objects.get(id=project_id)
            return queryset.filter(project=project)
        except (Project.DoesNotExist, DjangoValidationError):
            raise ValidationError({"project": _("Project not found")})

    def _apply_library_filter(self, queryset, statuses, library, against_library):
        if not library:
            return self.filter_no_library(queryset, statuses)
        return self.filter_for_library(queryset, statuses, library, against_library)

    def _apply_positioning_filter(self, request, queryset):
        positioning_filter_value = int(request.query_params.get(self.positioning_filter_param, 0))
        if not positioning_filter_value:
            return queryset

        if positioning_filter_value == PositioningFilter.POSITIONING_ONLY:
            return queryset.filter(status=ResourceStatus.POSITIONING, arbitration=Arbitration.NONE)
        elif positioning_filter_value == PositioningFilter.INSTRUCTION_NOT_STARTED:
            return queryset.filter(status=ResourceStatus.INSTRUCTION_BOUND, arbitration=Arbitration.NONE)

        return queryset

    def _apply_arbitration_filter(self, request, queryset):
        arbitration_param_value = request.query_params.get(self.arbitration_param, "").lower()
        if not arbitration_param_value:
            return queryset

        if arbitration_param_value == "1":
            return queryset.filter(arbitration=Arbitration.ONE)
        elif arbitration_param_value == "0":
            return queryset.filter(arbitration=Arbitration.ZERO)
        elif arbitration_param_value == "all":
            return queryset.filter(arbitration__in=[Arbitration.ZERO, Arbitration.ONE])
        else:
            raise ValidationError({"arbitration": _("Invalid arbitration param, must be '0', '1' or 'all'")})

    def _get_segments_annotation(self):
        return Exists(Resource.objects.filter(id=OuterRef("id"), collections__segments__isnull=False))

    def filter_for_library(self, queryset, statuses, library, against_library=None):
        # Ensure list
        if not isinstance(statuses, (list, tuple)):
            statuses = [statuses]

        need_has_segments = ResourceStatus.POSITIONING in statuses
        if need_has_segments:
            queryset = queryset.annotate(has_segments=self._get_segments_annotation())

        combined_q = Q()
        for s in statuses:
            if s == ResourceStatus.POSITIONING:
                combined_q |= Q(status=s, collections__library=library) | Q(
                    has_segments=False,
                    collections__library=library,
                )
            elif s == ResourceStatus.INSTRUCTION_BOUND:
                combined_q |= Q(
                    status=s,
                    collections__library=library,
                    instruction_turns__bound_copies__turns__0__library=str(library.id),
                    arbitration=Arbitration.NONE,
                )
            elif s == ResourceStatus.INSTRUCTION_UNBOUND:
                combined_q |= Q(
                    status=s,
                    collections__library=library,
                    instruction_turns__unbound_copies__turns__0__library=str(library.id),
                )
            elif s in [ResourceStatus.CONTROL_BOUND, ResourceStatus.CONTROL_UNBOUND]:
                combined_q |= Q(status=s, collections__library=library)
            else:
                # fallback to require collection membership for other statuses
                combined_q |= Q(status=s, collections__library=library)

        if combined_q:
            queryset = queryset.filter(combined_q).distinct()

        if against_library:
            queryset = queryset.filter(collections__library=against_library)

        return queryset

    def filter_no_library(self, queryset, statuses):
        if not isinstance(statuses, (list, tuple)):
            statuses = [statuses]

        need_has_segments = ResourceStatus.POSITIONING in statuses
        if need_has_segments:
            queryset = queryset.annotate(has_segments=self._get_segments_annotation())

        combined_q = Q()
        for s in statuses:
            if s == ResourceStatus.POSITIONING:
                combined_q |= Q(status=s) | Q(has_segments=False)
            elif s == ResourceStatus.INSTRUCTION_BOUND:
                combined_q |= Q(status=s, arbitration=Arbitration.NONE)
            elif s > ResourceStatus.POSITIONING:
                combined_q |= Q(status=s)

        if combined_q:
            queryset = queryset.filter(combined_q).distinct()

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
                    "pattern": UUID_REGEX,
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
                    "pattern": UUID_REGEX,
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
                    "pattern": UUID_REGEX,
                },
            },
            {
                "name": self.status_param,
                "required": True,
                "in": "query",
                "description": str(self.status_param_description)
                + "<br/>"
                + "<br/>".join([f"{_val}: {_label}" for _val, _label in ResourceStatus.choices]),
                "schema": {
                    "type": "array",
                    "items": {
                        "type": "integer",
                        "enum": [_r[0] for _r in ResourceStatus.choices],
                    },
                },
            },
            {
                "name": self.arbitration_param,
                "required": False,
                "in": "query",
                "description": str(self.arbitration_param_description),
                "schema": {
                    "type": "string",
                    "enum": ["0", "1", "all"],
                    "description": _(
                        "'0' for arbitration type 0, '1' for arbitration type 1, 'all' for all arbitration types"
                    ),
                },
            },
            {
                "name": self.positioning_filter_param,
                "required": False,
                "in": "query",
                "description": str(self.positioning_filter_description),
                "schema": {
                    "type": "integer",
                    "enum": [_p[0] for _p in PositioningFilter.choices],
                    "description": _("'10' for Positioning only, '20' for Instruction not start"),
                },
            },
        ]
