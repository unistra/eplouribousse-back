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

        cache.set(cache_key, data, timeout=base_settings.CACHE_TIMEOUT_DASHBOARD)
        return data

    def get_cache_key(self, project):
        """Generate cache key for this serializer section."""
        section_name = self.__class__.__name__.replace("Serializer", "").lower()
        return f"dashboard_{project.id}_{section_name}"


class InitialDataSerializer(DirectComputeMixin, serializers.Serializer):
    """
    Number of initial Collections before positioning
    Number of initial Resources before positioning
    """

    initial_collections = serializers.IntegerField(read_only=True)
    initial_resources = serializers.IntegerField(read_only=True)

    def compute_data(self, project):
        return {
            "title": _("Initial Datas"),
            _("Initial collections number before positioning"): Collection.objects.filter(project=project).count(),
            _("Initial resources number before positioning"): Resource.objects.filter(project=project).count(),
            "computed_at": timezone.now(),
        }


class PositioningInformationSerializer(DirectComputeMixin, serializers.Serializer):
    positioned_collections = serializers.IntegerField(read_only=True)
    positioned_collections_without_exclusion = serializers.IntegerField(read_only=True)
    collections_remaining_to_be_positioned = serializers.IntegerField(read_only=True)
    """
    Number of collections positioned (exclusions included)
    Number of collections positioned (exclusions excluded)
    Number of collections remaining to be positioned
    """

    def compute_data(self, project):
        return {
            "title": _("Positioning Information"),
            _("Number of Collections positioned (exclusions included)"): Collection.objects.filter(
                project=project, position__isnull=False
            ).count(),
            _("Number of Collections positioned (excluding exclusions)"): Collection.objects.filter(
                project=project, position__gt=0
            )
            .exclude(resource__status=ResourceStatus.EXCLUDED)
            .count(),
            _("Number of Collections remaining to be positioned"): Collection.objects.filter(
                project=project, position__isnull=True
            ).count(),
            "computed_at": timezone.now(),
        }


class ExclusionInformationSerializer(DirectComputeMixin, serializers.Serializer):
    """
    Excluded collections (by exclusion of collections or resources)
    Excluded resources
    """

    excluded_collections = serializers.IntegerField(read_only=True)
    excluded_resources = serializers.IntegerField(read_only=True)

    def compute_data(self, project):
        return {
            "title": _("Exclusion Information"),
            _("Number of excluded collections"): Collection.objects.filter(
                project=project,
                position=0,
            )
            .exclude(
                resource__status=ResourceStatus.EXCLUDED
            )  # todo: vérifier s'il faut exclure de l'exclusion les collections d'une ressource non participante (i.e. exclue)
            .count(),
            _("Number of resources discarded due to collection exclusion"): Resource.objects.filter(
                project=project,
                status=ResourceStatus.EXCLUDED,
            ).count(),
            "computed_at": timezone.now(),
        }


class ArbitrationInformationSerializer(DirectComputeMixin, serializers.Serializer):
    """
    Number of Collections in arbitration type 0
    Number of Collections in arbitration type 1
    Number of Resources affected by any arbitration type
    """

    collections_in_arbitration_0 = serializers.IntegerField(read_only=True)
    collections_in_arbitration_1 = serializers.IntegerField(read_only=True)
    resources_with_arbitration = serializers.IntegerField(read_only=True)

    def compute_data(self, project):
        return {
            "title": _("Arbitration Information"),
            _("Number of Collections in type 0 arbitration"): Collection.objects.filter(
                project=project, resource__arbitration=Arbitration.ZERO
            ).count(),
            _("Number of Collections in type 1 arbitration"): Collection.objects.filter(
                project=project, resource__arbitration=Arbitration.ONE
            ).count(),
            _("Number of Resources affected by any arbitration"): Resource.objects.filter(
                project=project, arbitration__in=[Arbitration.ZERO, Arbitration.ONE]
            ).count(),
            "computed_at": timezone.now(),
        }


class InstructionCandidatesInformationSerializer(CacheDashboardMixin, serializers.Serializer):
    """
    Information on candidates for instruction
    - Number of collections eligible for instruction
    - Number of resources eligible for instruction
      - of which Number of duplicates, triplicates, etc.
    """

    collections_candidates_for_instruction = serializers.IntegerField(read_only=True)
    resources_candidates_for_instruction = serializers.IntegerField(read_only=True)

    duplicates_in_ressource = serializers.IntegerField(read_only=True)
    duplicates_in_ressource_ratio = serializers.FloatField(read_only=True)

    triplicates_in_ressource = serializers.IntegerField(read_only=True)
    triplicates_in_ressource_ratio = serializers.FloatField(read_only=True)

    quadruplicates_in_ressource = serializers.IntegerField(read_only=True)
    quadruplicates_in_ressource_ratio = serializers.FloatField(read_only=True)

    other_higher_multiplicates_in_ressource = serializers.IntegerField(read_only=True)
    other_higher_multiplicates_in_ressource_ratio = serializers.FloatField(read_only=True)

    def compute_data(self, project):
        resources_with_segmented_collections = Resource.objects.filter(
            project=project, collections__segments__isnull=False
        ).values_list("id", flat=True)

        candidate_resources = Resource.objects.filter(
            project=project,
            status=ResourceStatus.INSTRUCTION_BOUND,
        ).exclude(
            id__in=resources_with_segmented_collections  # exclude resources with segmented collections
        )

        candidate_collections = Collection.objects.filter(resource__in=candidate_resources).exclude(position=0)

        # Group candidate collections by their resource 'code' and count occurrences.
        code_qs = (
            candidate_collections.values("resource__code")
            # transform the query into a group by resource__code field with a count of each group:
            # e.g.: [{"resource__code": "ABC123", "count": 3}, {"resource__code": "XYZ000", "count": 2}]
            .annotate(count=Count("id"))
            .filter(count__gt=1)
        )

        duplicates = code_qs.filter(count=2).count()
        triplicates = code_qs.filter(count=3).count()
        quadruplicates = code_qs.filter(count=4).count()
        other_higher_multiplicates = code_qs.filter(count__gt=4).count()

        candidate_resources = candidate_resources.count()

        def calculate_ratio(count, total):
            if total == 0:
                return 0.0
            return round((count / total) * 100, 1)

        return {
            "title": _("Information on candidates for instruction"),
            _("Number of collections eligible for instruction"): candidate_collections.count(),
            _("Number of resources eligible for instruction"): candidate_resources,
            _(
                "- of which Number of duplicates"
            ): f"{duplicates} ({calculate_ratio(duplicates, candidate_resources)} %)",
            _(
                "- of which Number of triplicates"
            ): f"{triplicates} ({calculate_ratio(triplicates, candidate_resources)} %)",
            _(
                "- of which Number of quadruplicates"
            ): f"{quadruplicates} ({calculate_ratio(quadruplicates, candidate_resources)} %)",
            _(
                "- of which Other higher multiples"
            ): f"{other_higher_multiplicates} ({calculate_ratio(other_higher_multiplicates, candidate_resources)} %)",
            "computed_at": timezone.now(),
        }


class InstructionsInformationSerializer(DirectComputeMixin, serializers.Serializer):
    """
    Number of resources for which instruction of related elements is in progress
    Number of resources for which instruction of unrelated elements is in progress
    Number of resources fully instructed (control performed)
    """

    ressources_with_status_instruction_bound = serializers.IntegerField(read_only=True)
    ressources_with_status_instruction_unbound = serializers.IntegerField(read_only=True)
    ressources_with_instruction_completed = serializers.IntegerField(read_only=True)

    def compute_data(self, project):
        return {
            "title": _("Information about instructions"),
            _("Number of resources for which instruction of bound elements is in progress"): Resource.objects.filter(
                project=project,
                status=ResourceStatus.INSTRUCTION_BOUND,
            ).count(),
            _("Number of resources for which instruction of unbound elements is in progress"): Resource.objects.filter(
                project=project,
                status=ResourceStatus.INSTRUCTION_UNBOUND,
            ).count(),
            _("Number of resources fully instructed (control performed)"): Resource.objects.filter(
                project=project,
                status=ResourceStatus.EDITION,
            ).count(),
            "computed_at": timezone.now(),
        }


class ControlsInformationSerializer(DirectComputeMixin, serializers.Serializer):
    ressources_with_bound_copies_being_controlled_count = serializers.IntegerField(read_only=True)
    ressources_with_unbound_copies_being_controlled_count = serializers.IntegerField(read_only=True)

    def compute_data(self, project):
        return {
            "title": _("Information about controls"),
            _("Number of resources for which bound elements are being controlled"): Resource.objects.filter(
                project=project,
                status=ResourceStatus.CONTROL_BOUND,
            ).count(),
            _("Number of resources for which unbound elements are being controlled"): Resource.objects.filter(
                project=project,
                status=ResourceStatus.CONTROL_UNBOUND,
            ).count(),
            "computed_at": timezone.now(),
        }


class AnomaliesInformationSerializer(DirectComputeMixin, serializers.Serializer):
    anomalies_in_progress = serializers.IntegerField(read_only=True)

    def compute_data(self, project):
        anomalies_in_progress = Anomaly.objects.filter(
            resource__project=project,
            fixed=False,
        ).count()

        return {
            "title": _("Information about anomalies"),
            _("Number of anomalies in progress"): anomalies_in_progress,
            "computed_at": timezone.now(),
        }


class AchievementsInformationSerializer(CacheDashboardMixin, serializers.Serializer):
    """
    Relative achievement (resources processed/number of resources eligible for instruction)
     - processed resources = all resources eligible for instruction AND that have passed the final control
    Absolute achievement (resources no longer to be processed/number of initial resources before positioning)
    - resources no longer to be processed = processed resources + resources discarded by collection exclusion
    """

    relative_completion = serializers.FloatField(read_only=True)
    absolute_completion = serializers.FloatField(read_only=True)

    def compute_data(self, project):
        processed_resources = Resource.objects.filter(
            project=project,
            status=ResourceStatus.EDITION,
        ).count()

        eligible_resources_for_instruction = (
            Resource.objects.filter(
                project=project,
            )
            .exclude(
                status=ResourceStatus.EXCLUDED,
            )
            .count()
        )

        excluded_resources = Resource.objects.filter(
            project=project,
            status=ResourceStatus.EXCLUDED,
        ).count()

        resources_no_longer_to_be_processed = processed_resources + excluded_resources
        initial_resources = Resource.objects.filter(project=project).count()

        relative_completion = (
            round((processed_resources / eligible_resources_for_instruction) * 100, 2)
            if eligible_resources_for_instruction > 0
            else 0.0
        )
        absolute_completion = (
            round((resources_no_longer_to_be_processed / initial_resources) * 100, 2) if initial_resources > 0 else 0.0
        )

        return {
            "title": _("Achievements"),
            _("Relative completion"): f"{relative_completion} %",
            _("Absolute completion"): f"{absolute_completion} %",
            "computed_at": timezone.now(),
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

            labels.append(library.name)
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
            "computed_at": timezone.now(),
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
        labels = [lib.name for lib in libraries]

        base_queryset = Resource.objects.filter(project=project)

        bound_counts = {}
        unbound_counts = {}
        for library in libraries:
            lib_name = library.name
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

            bound_counts[lib_name] = base_queryset.filter(bound_q).distinct().count()
            unbound_counts[lib_name] = base_queryset.filter(unbound_q).distinct().count()

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
            "computed_at": timezone.now(),
        }


class CollectionOccurrencesChartSerializer(CacheDashboardMixin, serializers.Serializer):
    """
    Prepares data for a bar chart showing the percentage distribution of resource
    multiplicities (doubles, triples, etc.) among instruction candidates.
    """

    def compute_data(self, project):
        # get candidates ressources
        resources_with_segmented_collections = Resource.objects.filter(
            project=project, collections__segments__isnull=False
        ).values_list("id", flat=True)

        candidate_resources = Resource.objects.filter(
            project=project,
            status=ResourceStatus.INSTRUCTION_BOUND,
        ).exclude(id__in=resources_with_segmented_collections)

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
            "title": _("Distribution of the number of occurrences in the collections eligible for the instruction"),
            "labels": labels,
            "datasets": [
                {
                    "label": _("Distribution of occurrence types"),
                    "data": data,
                }
            ],
            "computed_at": timezone.now(),
        }
