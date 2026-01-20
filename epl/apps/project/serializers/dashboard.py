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


class NonSingletonHelperMixin:
    """
    Separates resources and collections eligible for deduplication
    (resources with more than one collection per resource, collections not alone in their resource) from those that are not.
    Caches eligible/ineligible resources and collections in Redis for 2 minutes
    """

    CACHE_TIMEOUT = 120

    def _get_cache_key(self, project, data_type):
        # section = name of the current serializer, consistent with CacheDashboardMixin
        section_name = self.__class__.__name__.replace("Serializer", "").lower()
        tenant_id = self.context.get("request").tenant.id if self.context.get("request") else "no-tenant"
        key_name = f"dashboard_{tenant_id}:{project.id}:{section_name}:{data_type}"
        return md5(key_name.encode("utf-8"), usedforsecurity=False).hexdigest()

    def resources_eligible_for_deduplication(self, project):
        cache_key = self._get_cache_key(project, "resources_eligible")
        cached_ids = cache.get(cache_key)
        if cached_ids is not None:
            return Resource.objects.filter(id__in=cached_ids)

        qs = (
            Resource.objects.filter(project=project)
            .annotate(collections_count=Count("collections", distinct=True))
            .filter(collections_count__gt=1)
        )
        cache.set(cache_key, list(qs.values_list("id", flat=True)), timeout=self.CACHE_TIMEOUT)
        return qs

    def collections_eligible_for_deduplication(self, project):
        cache_key = self._get_cache_key(project, "collections_eligible")
        cached_ids = cache.get(cache_key)
        if cached_ids is not None:
            return Collection.objects.filter(id__in=cached_ids)

        qs = Collection.objects.filter(resource__in=self.resources_eligible_for_deduplication(project))
        cache.set(cache_key, list(qs.values_list("id", flat=True)), timeout=self.CACHE_TIMEOUT)
        return qs

    def resources_ineligible_for_deduplication(self, project):
        cache_key = self._get_cache_key(project, "resources_ineligible")
        cached_ids = cache.get(cache_key)
        if cached_ids is not None:
            return Resource.objects.filter(id__in=cached_ids)

        qs = (
            Resource.objects.filter(project=project)
            .annotate(collections_count=Count("collections", distinct=True))
            .filter(collections_count=1)
        )
        cache.set(cache_key, list(qs.values_list("id", flat=True)), timeout=self.CACHE_TIMEOUT)
        return qs

    def collections_ineligible_for_deduplication(self, project):
        cache_key = self._get_cache_key(project, "collections_ineligible")
        cached_ids = cache.get(cache_key)
        if cached_ids is not None:
            return Collection.objects.filter(id__in=cached_ids)

        qs = Collection.objects.filter(resource__in=self.resources_ineligible_for_deduplication(project))
        cache.set(cache_key, list(qs.values_list("id", flat=True)), timeout=self.CACHE_TIMEOUT)
        return qs

    def count_resources_eligible_for_deduplication(self, project):
        return self.resources_eligible_for_deduplication(project).count()

    def count_collections_eligible_for_deduplication(self, project):
        return self.collections_eligible_for_deduplication(project).count()

    def count_resources_ineligible_for_deduplication(self, project):
        return self.resources_ineligible_for_deduplication(project).count()

    def count_collections_ineligible_for_deduplication(self, project):
        return self.collections_ineligible_for_deduplication(project).count()


class InitialDataSerializer(NonSingletonHelperMixin, DirectComputeMixin, serializers.Serializer):
    def compute_data(self, project):
        return {
            "title": _("Initial data"),
            "computations": [
                {
                    "key": "initial_collections_count",
                    "label": _("Number of initial collections before positioning (without singletons)"),
                    "value": self.count_collections_eligible_for_deduplication(project),
                },
                {
                    "key": "initial_resources_count",
                    "label": _(
                        "Number of initial resources before positioning (without resources containing single collections)"
                    ),
                    "value": self.count_resources_eligible_for_deduplication(project),
                },
                {
                    "key": "singletons_count",
                    "label": _("Number of singletons (collections unique in a resource)"),
                    "value": self.count_collections_ineligible_for_deduplication(project),
                },
            ],
        }


class PositioningInformationSerializer(NonSingletonHelperMixin, DirectComputeMixin, serializers.Serializer):
    """
    Number of collections positioned (exclusions included)
    Number of collections positioned (exclusions excluded)
    Number of collections remaining to be positioned
    (Singletons excluded from all counts)
    """

    def compute_data(self, project):
        collections_eligible_for_deduplication = self.collections_eligible_for_deduplication(project)

        return {
            "title": _("Positioning Information"),
            "computations": [
                {
                    "key": "positioned_collections_exclusions_included",
                    "label": _("Number of Collections positioned (exclusions included)"),
                    "value": collections_eligible_for_deduplication.filter(position__isnull=False).count(),
                },
                {
                    "key": "positioned_collections_exclusions_excluded",
                    "label": _("Number of Collections positioned (excluding exclusions)"),
                    "value": collections_eligible_for_deduplication.filter(position__gt=0)
                    .exclude(resource__status=ResourceStatus.EXCLUDED)
                    .count(),
                },
                {
                    "key": "collections_remaining_to_position",
                    "label": _("Number of Collections remaining to be positioned"),
                    "value": collections_eligible_for_deduplication.filter(position__isnull=True).count(),
                },
            ],
        }


class ExclusionInformationSerializer(NonSingletonHelperMixin, DirectComputeMixin, serializers.Serializer):
    """
    Excluded collections (by exclusion of collections or resources)
    Excluded resources (by exclusion of collections)
    (Singletons excluded from all counts)
    """

    def compute_data(self, project):
        collections_eligible_for_deduplication = self.collections_eligible_for_deduplication(project)
        resources_eligible_for_deduplication = self.resources_eligible_for_deduplication(project)

        return {
            "title": _("Exclusion Information"),
            "computations": [
                {
                    "key": "excluded_collections",
                    "label": _("Number of excluded collections"),
                    "value": collections_eligible_for_deduplication.filter(
                        Q(position=0) | Q(resource__status=ResourceStatus.EXCLUDED)
                    )
                    .distinct()
                    .count(),
                },
                {
                    "key": "excluded_resources",
                    "label": _("Number of resources discarded due to collection exclusion"),
                    "value": resources_eligible_for_deduplication.filter(status=ResourceStatus.EXCLUDED).count(),
                },
            ],
        }


class ArbitrationInformationSerializer(NonSingletonHelperMixin, DirectComputeMixin, serializers.Serializer):
    """
    Number of Collections in arbitration type 0
    Number of Collections in arbitration type 1
    Number of Resources affected by any arbitration type
    (Singletons excluded from all counts)
    """

    def compute_data(self, project):
        collections_eligible_for_deduplication = self.collections_eligible_for_deduplication(project)
        resources_eligible_for_deduplication = self.resources_eligible_for_deduplication(project)

        return {
            "title": _("Arbitration Information"),
            "computations": [
                {
                    "key": "collections_arbitration_type_0",
                    "label": _("Number of Collections in type 0 arbitration"),
                    "value": collections_eligible_for_deduplication.filter(
                        resource__arbitration=Arbitration.ZERO
                    ).count(),
                },
                {
                    "key": "collections_arbitration_type_1",
                    "label": _("Number of Collections in type 1 arbitration"),
                    "value": collections_eligible_for_deduplication.filter(
                        resource__arbitration=Arbitration.ONE
                    ).count(),
                },
                {
                    "key": "resources_with_arbitration",
                    "label": _("Number of Resources affected by any arbitration"),
                    "value": resources_eligible_for_deduplication.filter(
                        arbitration__in=[Arbitration.ZERO, Arbitration.ONE]
                    ).count(),
                },
            ],
        }


class InstructionCandidatesInformationSerializer(NonSingletonHelperMixin, CacheDashboardMixin, serializers.Serializer):
    """
    Information on candidates for instruction
    - Number of collections eligible for instruction
    - Number of resources eligible for instruction
      - of which Number of duplicates, triplicates, etc.
    (Singletons excluded from all counts)
    """

    def compute_data(self, project):
        """
        Candidate resources for instruction:
        - have all their collections positioned (position = 0, 1, 2, 3 or 4)
        - is not in arbitration status
        - is not excluded (not ResourceStatus.EXCLUDED)
        i.e. resource.Status >= ResourceStatus.INSTRUCTION_BOUND
        - AND belong to resources_eligible_for_deduplication (>1 collection)

        Candidate collections for instruction:
        - belongs to a candidate resource for instruction
        - are not excluded (position != 0)
        - AND belong to collections_eligible_for_deduplication
        """
        resources_eligible_for_deduplication = self.resources_eligible_for_deduplication(project)
        collections_eligible_for_deduplication = self.collections_eligible_for_deduplication(project)

        # Candidate resources: instruction_bound status + eligible for deduplication
        resources_candidate_for_instruction = resources_eligible_for_deduplication.filter(
            status__gte=ResourceStatus.INSTRUCTION_BOUND,
        )

        # Candidate collections: not excluded + eligible for deduplication
        collections_candidate_for_instruction = collections_eligible_for_deduplication.filter(
            resource__in=resources_candidate_for_instruction
        ).exclude(position=0)

        # Group by resource code and count occurrences
        code_qs = (
            collections_candidate_for_instruction.values("resource__code")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
        )

        duplicates = code_qs.filter(count=2).count()
        triplicates = code_qs.filter(count=3).count()
        quadruplicates = code_qs.filter(count=4).count()
        other_multiples = code_qs.filter(count__gt=4).count()

        total_resources_candidate_for_instruction = resources_candidate_for_instruction.count()

        def calculate_ratio(count, total):
            return round((count / total) * 100, 1) if total > 0 else 0.0

        return {
            "title": _("Information on candidates for instruction (upcoming, in progress, or completed)"),
            "computations": [
                {
                    "key": "collections_eligible_for_instruction",
                    "label": _("Number of collections eligible for instruction"),
                    "value": collections_candidate_for_instruction.count(),
                },
                {
                    "key": "resources_eligible_for_instruction",
                    "label": _("Number of resources eligible for instruction"),
                    "value": total_resources_candidate_for_instruction,
                },
                {
                    "key": "duplicates_count",
                    "label": _("- of which Number of duplicates"),
                    "value": duplicates,
                    "ratio": calculate_ratio(duplicates, total_resources_candidate_for_instruction),
                },
                {
                    "key": "triplicates_count",
                    "label": _("- of which Number of triplicates"),
                    "value": triplicates,
                    "ratio": calculate_ratio(triplicates, total_resources_candidate_for_instruction),
                },
                {
                    "key": "quadruplicates_count",
                    "label": _("- of which Number of quadruplicates"),
                    "value": quadruplicates,
                    "ratio": calculate_ratio(quadruplicates, total_resources_candidate_for_instruction),
                },
                {
                    "key": "other_multiples_count",
                    "label": _("- of which Other higher multiples"),
                    "value": other_multiples,
                    "ratio": calculate_ratio(other_multiples, total_resources_candidate_for_instruction),
                },
            ],
        }


class InstructionsInformationSerializer(NonSingletonHelperMixin, DirectComputeMixin, serializers.Serializer):
    """
    Number of resources for which instruction of related elements is in progress
    Number of resources for which instruction of unrelated elements is in progress
    Number of resources fully instructed (control performed)
    (Singletons excluded from all counts)
    """

    def compute_data(self, project):
        resources_eligible_for_deduplication = self.resources_eligible_for_deduplication(project)

        return {
            "title": _("Information about ongoing instructions"),
            "computations": [
                {
                    "key": "resources_instruction_bound",
                    "label": _("Number of resources for which instruction of bound elements is in progress"),
                    "value": resources_eligible_for_deduplication.filter(
                        status=ResourceStatus.INSTRUCTION_BOUND
                    ).count(),
                },
                {
                    "key": "resources_instruction_unbound",
                    "label": _("Number of resources for which instruction of unbound elements is in progress"),
                    "value": resources_eligible_for_deduplication.filter(
                        status=ResourceStatus.INSTRUCTION_UNBOUND
                    ).count(),
                },
                {
                    "key": "resources_instruction_completed",
                    "label": _("Number of resources fully instructed (control performed)"),
                    "value": resources_eligible_for_deduplication.filter(status=ResourceStatus.EDITION).count(),
                },
            ],
        }


class ControlsInformationSerializer(NonSingletonHelperMixin, DirectComputeMixin, serializers.Serializer):
    """
    Information about controls
    (Singletons excluded from all counts)
    """

    def compute_data(self, project):
        resources_eligible_for_deduplication = self.resources_eligible_for_deduplication(project)

        return {
            "title": _("Information about controls"),
            "computations": [
                {
                    "key": "resources_control_bound",
                    "label": _("Number of resources for which bound elements are being controlled"),
                    "value": resources_eligible_for_deduplication.filter(status=ResourceStatus.CONTROL_BOUND).count(),
                },
                {
                    "key": "resources_control_unbound",
                    "label": _("Number of resources for which unbound elements are being controlled"),
                    "value": resources_eligible_for_deduplication.filter(status=ResourceStatus.CONTROL_UNBOUND).count(),
                },
            ],
        }


class AnomaliesInformationSerializer(NonSingletonHelperMixin, DirectComputeMixin, serializers.Serializer):
    """
    Information about anomalies
    (Singletons excluded from all counts)
    """

    def compute_data(self, project):
        resources_eligible_for_deduplication = self.resources_eligible_for_deduplication(project)

        return {
            "title": _("Information about anomalies"),
            "computations": [
                {
                    "key": "anomalies_in_progress",
                    "label": _("Number of anomalies in progress"),
                    "value": Anomaly.objects.filter(
                        resource__in=resources_eligible_for_deduplication, fixed=False
                    ).count(),
                }
            ],
        }


class AchievementsInformationSerializer(NonSingletonHelperMixin, CacheDashboardMixin, serializers.Serializer):
    """
    Relative achievement (processed resources / candidate ressources for instruction)
     - processed resources = resources eligible for deduplication AND eligible for instruction AND that have passed the final control (status EDITION)
    Absolute achievement (processed + excluded resources / initial resources eligible for deduplication)
    (Singletons excluded from all counts)
    """

    def compute_data(self, project):
        resources_eligible_for_deduplication = self.resources_eligible_for_deduplication(project)

        # Candidate resources for instruction: status >= INSTRUCTION_BOUND
        resources_candidate_for_instruction = resources_eligible_for_deduplication.filter(
            status__gte=ResourceStatus.INSTRUCTION_BOUND,
        )
        total_resources_candidate_for_instruction = resources_candidate_for_instruction.count()

        # Processed resources: status = EDITION
        processed_resources = resources_eligible_for_deduplication.filter(status=ResourceStatus.EDITION).count()

        # Excluded resources
        excluded_resources = resources_eligible_for_deduplication.filter(status=ResourceStatus.EXCLUDED).count()

        # Initial resources eligible for deduplication
        initial_resources_eligible_for_deduplication = self.count_resources_eligible_for_deduplication(project)

        # Resources no longer to be processed
        resources_no_longer_to_be_processed = processed_resources + excluded_resources

        # Relative completion: processed / candidates for instruction
        relative_completion = (
            round((processed_resources / total_resources_candidate_for_instruction) * 100, 2)
            if total_resources_candidate_for_instruction > 0
            else 0.0
        )

        # Absolute completion: (processed + excluded) / initial
        absolute_completion = (
            round((resources_no_longer_to_be_processed / initial_resources_eligible_for_deduplication) * 100, 2)
            if initial_resources_eligible_for_deduplication > 0
            else 0.0
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


class RealizedPositioningChartSerializer(NonSingletonHelperMixin, CacheDashboardMixin, serializers.Serializer):
    """
    Prepares data for a bar chart showing positioning progress per library.
    Formatted for Chart.js (labels and data only).

    Represents the number of positionings carried out as a percentage by library
    (excluding resources discarded by collection exclusion and excluding resources containing a single collection).
    For each library, 100% represents the number of collections eligible for deduplication.
    (Singletons excluded from all counts)
    """

    def compute_data(self, project):
        # Get all libraries involved in the project
        libraries = project.libraries.distinct()
        collections_eligible_for_deduplication = self.collections_eligible_for_deduplication(project)

        labels = []
        realized_positionings_by_libraries_percentage = []
        errors = []

        for library in libraries:
            # Denominator: Total collections for this library in this project,
            # already filtered to exclude singletons and excluded resources
            collections_in_library = collections_eligible_for_deduplication.filter(library=library).exclude(
                resource__status=ResourceStatus.EXCLUDED
            )

            denom = collections_in_library.count()
            if denom == 0:
                errors.append(_("No collection in library '%(library_name)s'") % {"library_name": library.name})
                continue

            # Numerator: Collections that are effectively positioned (position >= 0)
            positioned_collections_in_library = collections_in_library.filter(position__gte=0).count()

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


class ResourcesToInstructChartSerializer(NonSingletonHelperMixin, CacheDashboardMixin, serializers.Serializer):
    """
    Prepares data for a stacked bar chart showing resources to be instructed
    (bound vs unbound) per library. Formatted for Chart.js.
    The count is based on resources eligible for deduplication and filtered with the same constraints as ResourceFilter.
    (Singletons excluded from all counts)
    """

    def compute_data(self, project):
        libraries = project.libraries.distinct().order_by("name")
        labels = [lib.alias for lib in libraries]

        resources_eligible_for_deduplication = self.resources_eligible_for_deduplication(project)

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

            bound_counts[lib_alias] = resources_eligible_for_deduplication.filter(bound_q).distinct().count()
            unbound_counts[lib_alias] = resources_eligible_for_deduplication.filter(unbound_q).distinct().count()

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


class CollectionOccurrencesChartSerializer(NonSingletonHelperMixin, CacheDashboardMixin, serializers.Serializer):
    """
    Prepares data for a bar chart showing the percentage distribution of resource
    multiplicities (doubles, triples, etc.) among instruction candidates.
    (Singletons excluded from all counts)
    """

    def compute_data(self, project):
        resources_eligible_for_deduplication = self.resources_eligible_for_deduplication(project)
        collections_eligible_for_deduplication = self.collections_eligible_for_deduplication(project)

        # Get candidate resources for instruction (eligible for deduplication + instruction status)
        resources_candidate_for_instruction = resources_eligible_for_deduplication.filter(
            status__gte=ResourceStatus.INSTRUCTION_BOUND,
        )

        total_candidate_resources = resources_candidate_for_instruction.count()

        # Get candidate collections (eligible for deduplication + in candidate resources + not excluded)
        collections_candidate_for_instruction = collections_eligible_for_deduplication.filter(
            resource__in=resources_candidate_for_instruction
        ).exclude(position=0)

        # Group by resource code and count occurrences
        code_qs = (
            collections_candidate_for_instruction.values("resource__code")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
        )

        # Count occurrences
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
