from hashlib import md5

from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from epl.apps.project.models import Anomaly, ResourceStatus
from epl.apps.project.models.collection import Arbitration, Collection, Resource
from epl.settings import base as base_settings


class DirectComputeMixin:
    """
    Base mixin for dashboard serializers that compute data directly without caching.
    It calls the compute_data() method to get the data.
    """

    def to_representation(self, instance):
        project = instance
        return self.compute_data(project)

    def compute_data(self, project):
        """Compute dashboard data for the given project."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement compute_data() method")


class CacheDashboardMixin(DirectComputeMixin):
    """
    Base mixin for project dashboard serializers that provides caching.
    It inherits from DirectComputeMixin and adds a caching layer.
    """

    def to_representation(self, instance):
        project = instance
        cache_key = self.get_cache_key(project)

        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return cached_data

        data = super().to_representation(instance)

        # add computed_at field when caching
        if isinstance(data, dict):
            data["computed_at"] = timezone.now()

        cache.set(cache_key, data, timeout=base_settings.CACHE_TIMEOUT_DASHBOARD)
        return data

    def get_cache_key(self, project):
        """Generate cache key for this serializer section."""
        section_name = self.__class__.__name__.replace("Serializer", "").lower()
        tenant_id = self.context.get("request").tenant.id if self.context.get("request") else "no-tenant"
        key_name: str = f"dashboard_{tenant_id}:{project.id}:{section_name}"
        return md5(key_name.encode("utf-8"), usedforsecurity=False).hexdigest()


class InitialDataSerializer(DirectComputeMixin, serializers.Serializer):
    """
    Number of initial Collections before positioning
    Number of initial Resources before positioning
    """

    def compute_data(self, project):
        return {
            "title": _("Initial Datas"),
            "computations": [
                {
                    "key": "initial_collections_count",
                    "label": _("Initial collections number before positioning"),
                    "value": Collection.objects.filter(project=project).count(),
                },
                {
                    "key": "initial_resources_count",
                    "label": _("Initial resources number before positioning"),
                    "value": Resource.objects.filter(project=project).count(),
                },
            ],
        }


class PositioningInformationSerializer(DirectComputeMixin, serializers.Serializer):
    """
    Number of collections positioned (exclusions included)
    Number of collections positioned (exclusions excluded)
    Number of collections remaining to be positioned
    """

    def compute_data(self, project):
        return {
            "title": _("Positioning Information"),
            "computations": [
                {
                    "key": "positioned_collections_exclusions_included",
                    "label": _("Number of Collections positioned (exclusions included)"),
                    "value": Collection.objects.filter(project=project, position__isnull=False).count(),
                },
                {
                    "key": "positioned_collections_exclusions_excluded",
                    "label": _("Number of Collections positioned (excluding exclusions)"),
                    "value": Collection.objects.filter(project=project, position__gt=0)
                    .exclude(resource__status=ResourceStatus.EXCLUDED)
                    .count(),
                },
                {
                    "key": "collections_remaining_to_position",
                    "label": _("Number of Collections remaining to be positioned"),
                    "value": Collection.objects.filter(project=project, position__isnull=True).count(),
                },
            ],
        }


class ExclusionInformationSerializer(DirectComputeMixin, serializers.Serializer):
    """
    Excluded collections (by exclusion of collections or resources)
    Excluded resources (by exclusion of collections)
    """

    def compute_data(self, project):
        return {
            "title": _("Exclusion Information"),
            "computations": [
                {
                    "key": "excluded_collections",
                    "label": _("Number of excluded collections"),
                    "value": Collection.objects.filter(
                        Q(project=project) & (Q(position=0) | Q(resource__status=ResourceStatus.EXCLUDED))
                    )
                    .distinct()
                    .count(),
                },
                {
                    "key": "excluded_resources",
                    "label": _("Number of resources discarded due to collection exclusion"),
                    "value": Resource.objects.filter(project=project, status=ResourceStatus.EXCLUDED).count(),
                },
            ],
        }


class ArbitrationInformationSerializer(DirectComputeMixin, serializers.Serializer):
    """
    Number of Collections in arbitration type 0
    Number of Collections in arbitration type 1
    Number of Resources affected by any arbitration type
    """

    def compute_data(self, project):
        return {
            "title": _("Arbitration Information"),
            "computations": [
                {
                    "key": "collections_arbitration_type_0",
                    "label": _("Number of Collections in type 0 arbitration"),
                    "value": Collection.objects.filter(project=project, resource__arbitration=Arbitration.ZERO).count(),
                },
                {
                    "key": "collections_arbitration_type_1",
                    "label": _("Number of Collections in type 1 arbitration"),
                    "value": Collection.objects.filter(project=project, resource__arbitration=Arbitration.ONE).count(),
                },
                {
                    "key": "resources_with_arbitration",
                    "label": _("Number of Resources affected by any arbitration"),
                    "value": Resource.objects.filter(
                        project=project, arbitration__in=[Arbitration.ZERO, Arbitration.ONE]
                    ).count(),
                },
            ],
        }


class InstructionCandidatesInformationSerializer(CacheDashboardMixin, serializers.Serializer):
    """
    Information on candidates for instruction
    - Number of collections eligible for instruction
    - Number of resources eligible for instruction
      - of which Number of duplicates, triplicates, etc.
    """

    def compute_data(self, project):
        """
        Canditate resources for instruction :
        - have all their collections positioned (position = 0, 1, 2, 3 or 4)
        - is not in arbitration status
        - is not excluded (not ResourceStatus.EXCLUDED)
        i.e. resource.Status >= ResourceStatus.INSTRUCTION_BOUND

        Candidate collections for instruction :
        - belongs to a candidate resource for instruction
        - are not excluded
        """
        candidate_resources_qs = Resource.objects.filter(
            project=project,
            status__gte=ResourceStatus.INSTRUCTION_BOUND,
        )
        candidate_collections_qs = Collection.objects.filter(resource__in=candidate_resources_qs).exclude(position=0)

        code_qs = candidate_collections_qs.values("resource__code").annotate(count=Count("id")).filter(count__gt=1)

        duplicates = code_qs.filter(count=2).count()
        triplicates = code_qs.filter(count=3).count()
        quadruplicates = code_qs.filter(count=4).count()
        other_multiples = code_qs.filter(count__gt=4).count()

        total_candidate_resources = candidate_resources_qs.count()

        def calculate_ratio(count, total):
            return round((count / total) * 100, 1) if total > 0 else 0.0

        return {
            "title": _("Information on candidates for instruction (upcoming, in progress, or completed)"),
            "computations": [
                {
                    "key": "collections_eligible_for_instruction",
                    "label": _("Number of collections eligible for instruction"),
                    "value": candidate_collections_qs.count(),
                },
                {
                    "key": "resources_eligible_for_instruction",
                    "label": _("Number of resources eligible for instruction"),
                    "value": total_candidate_resources,
                },
                {
                    "key": "duplicates_count",
                    "label": _("- of which Number of duplicates"),
                    "value": duplicates,
                    "ratio": calculate_ratio(duplicates, total_candidate_resources),
                },
                {
                    "key": "triplicates_count",
                    "label": _("- of which Number of triplicates"),
                    "value": triplicates,
                    "ratio": calculate_ratio(triplicates, total_candidate_resources),
                },
                {
                    "key": "quadruplicates_count",
                    "label": _("- of which Number of quadruplicates"),
                    "value": quadruplicates,
                    "ratio": calculate_ratio(quadruplicates, total_candidate_resources),
                },
                {
                    "key": "other_multiples_count",
                    "label": _("- of which Other higher multiples"),
                    "value": other_multiples,
                    "ratio": calculate_ratio(other_multiples, total_candidate_resources),
                },
            ],
        }


class InstructionsInformationSerializer(DirectComputeMixin, serializers.Serializer):
    """
    Number of resources for which instruction of related elements is in progress
    Number of resources for which instruction of unrelated elements is in progress
    Number of resources fully instructed (control performed)
    """

    def compute_data(self, project):
        return {
            "title": _("Information about ongoing instructions"),
            "computations": [
                {
                    "key": "resources_instruction_bound",
                    "label": _("Number of resources for which instruction of bound elements is in progress"),
                    "value": Resource.objects.filter(project=project, status=ResourceStatus.INSTRUCTION_BOUND).count(),
                },
                {
                    "key": "resources_instruction_unbound",
                    "label": _("Number of resources for which instruction of unbound elements is in progress"),
                    "value": Resource.objects.filter(
                        project=project, status=ResourceStatus.INSTRUCTION_UNBOUND
                    ).count(),
                },
                {
                    "key": "resources_instruction_completed",
                    "label": _("Number of resources fully instructed (control performed)"),
                    "value": Resource.objects.filter(project=project, status=ResourceStatus.EDITION).count(),
                },
            ],
        }


class ControlsInformationSerializer(DirectComputeMixin, serializers.Serializer):
    def compute_data(self, project):
        return {
            "title": _("Information about controls"),
            "computations": [
                {
                    "key": "resources_control_bound",
                    "label": _("Number of resources for which bound elements are being controlled"),
                    "value": Resource.objects.filter(project=project, status=ResourceStatus.CONTROL_BOUND).count(),
                },
                {
                    "key": "resources_control_unbound",
                    "label": _("Number of resources for which unbound elements are being controlled"),
                    "value": Resource.objects.filter(project=project, status=ResourceStatus.CONTROL_UNBOUND).count(),
                },
            ],
        }


class AnomaliesInformationSerializer(DirectComputeMixin, serializers.Serializer):
    def compute_data(self, project):
        return {
            "title": _("Information about anomalies"),
            "computations": [
                {
                    "key": "anomalies_in_progress",
                    "label": _("Number of anomalies in progress"),
                    "value": Anomaly.objects.filter(resource__project=project, fixed=False).count(),
                }
            ],
        }


class AchievementsInformationSerializer(CacheDashboardMixin, serializers.Serializer):
    """
    Relative achievement (resources processed/number of resources eligible for instruction)
     - processed resources = all resources eligible for instruction AND that have passed the final control
    Absolute achievement (resources no longer to be processed/number of initial resources before positioning)
    - resources no longer to be processed = processed resources + resources discarded by collection exclusion
    """

    def compute_data(self, project):
        processed_resources = Resource.objects.filter(project=project, status=ResourceStatus.EDITION).count()
        eligible_resources = Resource.objects.filter(project=project).exclude(status=ResourceStatus.EXCLUDED).count()
        excluded_resources = Resource.objects.filter(project=project, status=ResourceStatus.EXCLUDED).count()
        initial_resources = Resource.objects.filter(project=project).count()

        resources_no_longer_to_be_processed = processed_resources + excluded_resources

        relative_completion = (
            round((processed_resources / eligible_resources) * 100, 2) if eligible_resources > 0 else 0.0
        )
        absolute_completion = (
            round((resources_no_longer_to_be_processed / initial_resources) * 100, 2) if initial_resources > 0 else 0.0
        )

        return {
            "title": _("Achievements"),
            "computations": [
                {
                    "key": "relative_completion",
                    "label": _("Relative completion"),
                    "value": relative_completion,
                    "unit": "%",
                },
                {
                    "key": "absolute_completion",
                    "label": _("Absolute completion"),
                    "value": absolute_completion,
                    "unit": "%",
                },
            ],
        }


class RealizedPositioningChartSerializer(CacheDashboardMixin, serializers.Serializer):
    """
    Prepares data for a bar chart showing positioning progress per library.
    Formatted for Chart.js (labels and data only).

    Represents the number of positionings carried out as a percentage by library (excluding resources discarded by collection exclusion).
    For each library, 100% represents the number of collections (excluding resources discarded by collection exclusion).
    """

    def compute_data(self, project):
        # Get all libraries involved in the project
        libraries = project.libraries.distinct()

        labels = []
        realized_positionings_by_libraries_percentage = []
        errors = []

        for library in libraries:
            # Denominator: Total collections for this library in this project,
            # excluding collections that are part of an already excluded resource.
            collections_in_library = Collection.objects.filter(project=project, library=library).exclude(
                resource__status=ResourceStatus.EXCLUDED
            )

            denom = collections_in_library.count()
            if denom == 0:
                errors.append(_("No collection in library '%(library_name)s'") % {"library_name": library.name})
                continue

            # Numerator: Collections that are effectively positioned (position >= 0)
            # The .exclude() on resource status is technically redundant if a positioned
            # collection cannot belong to an excluded resource, but it's safer.
            positioned_collections_in_library = (
                collections_in_library.filter(position__gte=0).exclude(resource__status=ResourceStatus.EXCLUDED).count()
            )
            percentage = round((positioned_collections_in_library / denom) * 100, 2)

            labels.append(library.alias)
            realized_positionings_by_libraries_percentage.append(percentage)

        result = {
            "title": _("% of realized positioning progress by library"),
            "labels": labels,
            "datasets": [
                {
                    "label": _("% of collections positioned"),
                    "data": realized_positionings_by_libraries_percentage,
                }
            ],
        }
        if errors:
            result["errors"] = errors
        return result


class ResourcesToInstructChartSerializer(CacheDashboardMixin, serializers.Serializer):
    """
    Prepares data for a stacked bar chart showing resources to be instructed
    (bound vs unbound) per library. Formatted for Chart.js.
    The count is based on resources filtered with the same constraints as ResourceFilter.
    """

    def compute_data(self, project):
        libraries = project.libraries.distinct().order_by("name")
        labels = [lib.alias for lib in libraries]

        base_queryset = Resource.objects.filter(project=project)

        bound_counts = {}
        unbound_counts = {}
        for library in libraries:
            lib_alias = library.alias
            lib_id_str = str(library.id)

            bound_q = Q(
                status=ResourceStatus.INSTRUCTION_BOUND,
                collections__library=library,
                instruction_turns__bound_copies__turns__0__library=lib_id_str,
                arbitration=Arbitration.NONE,
            )
            unbound_q = Q(
                status=ResourceStatus.INSTRUCTION_UNBOUND,
                collections__library=library,
                instruction_turns__unbound_copies__turns__0__library=lib_id_str,
            )

            bound_counts[lib_alias] = base_queryset.filter(bound_q).distinct().count()
            unbound_counts[lib_alias] = base_queryset.filter(unbound_q).distinct().count()

        return {
            "title": _("Number of resources to be instructed"),
            "labels": labels,
            "datasets": [
                {
                    "label": _("bound"),
                    "data": [bound_counts.get(label, 0) for label in labels],
                },
                {
                    "label": _("unbound"),
                    "data": [unbound_counts.get(label, 0) for label in labels],
                },
            ],
        }


class CollectionOccurrencesChartSerializer(CacheDashboardMixin, serializers.Serializer):
    """
    Prepares data for a bar chart showing the percentage distribution of resource
    multiplicities (doubles, triples, etc.) among instruction candidates.
    """

    def compute_data(self, project):
        # get candidates ressources
        candidate_resources = Resource.objects.filter(
            project=project,
            status__gte=ResourceStatus.INSTRUCTION_BOUND,
        )

        total_candidate_resources = candidate_resources.count()

        # get candidate collections
        candidate_collections = Collection.objects.filter(resource__in=candidate_resources).exclude(position=0)

        # group by resource code and count occurrences
        code_qs = candidate_collections.values("resource__code").annotate(count=Count("id")).filter(count__gt=1)

        # count occurrences
        doubles = code_qs.filter(count=2).count()
        triples = code_qs.filter(count=3).count()
        quadruples = code_qs.filter(count=4).count()
        others = code_qs.filter(count__gt=4).count()

        def to_percent(value, total):
            if total == 0:
                return 0.0
            return round((value / total) * 100, 2)

        labels = [
            _("duplicates"),
            _("triplicates"),
            _("quadruplicates"),
            _("more"),
        ]
        data = [
            to_percent(doubles, total_candidate_resources),
            to_percent(triples, total_candidate_resources),
            to_percent(quadruples, total_candidate_resources),
            to_percent(others, total_candidate_resources),
        ]

        return {
            "title": _("Distribution of the number of occurrences in the collections candidate for the instruction"),
            "labels": labels,
            "datasets": [
                {
                    "label": _("Distribution of occurrence types"),
                    "data": data,
                }
            ],
        }
