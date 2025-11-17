from django.core.cache import cache
from django.db.models import Count
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
            _("Computed at"): timezone.now(),
        }


class PositioningInformationSerializer(CacheDashboardMixin, serializers.Serializer):
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
            _("Computed at"): timezone.now(),
        }


class ExclusionInformationSerializer(CacheDashboardMixin, serializers.Serializer):
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
            _("Computed at"): timezone.now(),
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
            _("Computed at"): timezone.now(),
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
            _("Computed at"): timezone.now(),
        }


class InstructionsInformationSerializer(CacheDashboardMixin, serializers.Serializer):
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
            _("Computed at"): timezone.now(),
        }


class ControlsInformationSerializer(CacheDashboardMixin, serializers.Serializer):
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
        }


class AnomaliesInformationSerializer(CacheDashboardMixin, serializers.Serializer):
    anomalies_in_progress = serializers.IntegerField(read_only=True)

    def compute_data(self, project):
        anomalies_in_progress = Anomaly.objects.filter(
            resource__project=project,
            fixed=False,
        ).count()

        return {
            "title": _("Information about anomalies"),
            _("Number of anomalies in progress"): anomalies_in_progress,
            _("Computed at"): timezone.now(),
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
            _("Relative completion"): relative_completion,
            _("Absolute completion"): absolute_completion,
            _("Computed at"): timezone.now(),
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

        for library in libraries:
            # Denominator: Total collections for this library in this project,
            # excluding collections that are part of an already excluded resource.
            collections_in_library = Collection.objects.filter(project=project, library=library).exclude(
                resource__status=ResourceStatus.EXCLUDED
            )

            if collections_in_library.count == 0:
                continue

            # Numerator: Collections that are effectively positioned (position >= 0)
            # The .exclude() on resource status is technically redundant if a positioned
            # collection cannot belong to an excluded resource, but it's safer.
            positioned_collections_in_library = (
                collections_in_library.filter(position__gte=0).exclude(resource__status=ResourceStatus.EXCLUDED).count()
            )

            realized_positionings_by_library_percentage = round(
                (positioned_collections_in_library / collections_in_library.count()) * 100, 2
            )

            labels.append(library.name)
            realized_positionings_by_libraries_percentage.append(realized_positionings_by_library_percentage)

        return {
            "labels": labels,
            "datasets": [
                {
                    "label": "% de collections positionnées",  # question: en quelle langue gérer cette étiquette ?
                    "data": realized_positionings_by_libraries_percentage,
                }
            ],
            "computed_at": timezone.now(),
        }


class ResourcesToInstructChartSerializer(CacheDashboardMixin, serializers.Serializer):
    """
    Prepares data for a stacked bar chart showing resources to be instructed
    (bound vs unbound) per library. Formatted for Chart.js.
    The count is based on collections, as a proxy for workload per library.
    """

    def compute_data(self, project):
        # X-axis
        libraries = project.libraries.distinct().order_by("name")
        labels = [lib.name for lib in libraries]

        # --- Bound Resources (First Stack) ---
        # Count collections belonging to 'bound' resources, grouped by library name
        bound_data = {
            item["library__name"]: item["count"]
            for item in Collection.objects.filter(project=project, resource__status=ResourceStatus.INSTRUCTION_BOUND)
            .values("library__name")
            .annotate(count=Count("id"))
        }

        # --- Unbound Resources (Second Stack) ---
        # Count collections belonging to 'unbound' resources, grouped by library name
        unbound_data = {
            item["library__name"]: item["count"]
            for item in Collection.objects.filter(project=project, resource__status=ResourceStatus.INSTRUCTION_UNBOUND)
            .values("library__name")
            .annotate(count=Count("id"))
        }

        # Prepare the final data structure for Chart.js
        return {
            "labels": labels,
            "datasets": [
                {
                    "label": "dashboard.charts.to_instruct.bound_label",
                    "data": [bound_data.get(label, 0) for label in labels],
                },
                {
                    "label": "dashboard.charts.to_instruct.unbound_label",
                    "data": [unbound_data.get(label, 0) for label in labels],
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
        if total_candidate_resources == 0:
            return {"labels": [], "datasets": []}

        # get candidate collections
        candidate_collections = Collection.objects.filter(resource__in=candidate_resources).exclude(position=0)

        # group by resource code and count occurrences
        code_qs = (
            candidate_collections.values("resource__code")
            .annotate(count=Count("id"))
            .filter(count__gt=1)  # On ne s'intéresse qu'aux multiplicités (>= 2)
        )

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
            "dashboard.charts.occurrences.labels.doubles",
            "dashboard.charts.occurrences.labels.triples",
            "dashboard.charts.occurrences.labels.quadruples",
            "dashboard.charts.occurrences.labels.others",
        ]
        data = [
            to_percent(doubles, total_candidate_resources),
            to_percent(triples, total_candidate_resources),
            to_percent(quadruples, total_candidate_resources),
            to_percent(others, total_candidate_resources),
        ]

        return {
            "labels": labels,
            "datasets": [
                {
                    "label": "dashboard.charts.occurrences.dataset_label",
                    "data": data,
                }
            ],
            "computed_at": timezone.now(),
        }
