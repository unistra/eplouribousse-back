from django.core.cache import cache
from django.db.models import Count
from rest_framework import serializers

from epl.apps.project.models import Anomaly, ResourceStatus
from epl.apps.project.models.collection import Arbitration, Collection, Resource
from epl.settings import base as base_settings


class BaseDashboardMixin:
    """
    Base mixin for project dashboard serializers.

    Provides:
    - Automatic caching of computed data
    - Template method pattern for data computation

    Subclasses must implement compute_data(project) method.
    """

    def to_representation(self, instance):
        project = instance
        cache_key = self.get_cache_key(project)

        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return cached_data

        data = self.compute_data(project)

        cache.set(cache_key, data, timeout=base_settings.CACHE_TIMEOUT_DASHBOARD)
        return data

    def compute_data(self, project):
        """Compute dashboard data for the given project."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement compute_data() method")

    def get_cache_key(self, project):
        """Generate cache key for this serializer section."""
        section_name = self.__class__.__name__.replace("Serializer", "").lower()
        return f"dashboard_{project.id}_{section_name}"


class InitialDataSerializer(BaseDashboardMixin, serializers.Serializer):
    initial_collections_count = serializers.IntegerField(read_only=True)
    initial_resources_count = serializers.IntegerField(read_only=True)

    def compute_data(self, project):
        return {
            "initial_collections_count": Collection.objects.filter(project=project).count(),
            "initial_resources_count": Resource.objects.filter(project=project).count(),
        }


class PositioningInformationSerializer(BaseDashboardMixin, serializers.Serializer):
    positioned_collections_count = serializers.IntegerField(read_only=True)
    positioned_collections_without_exclusion_count = serializers.IntegerField(read_only=True)
    collections_remaining_to_be_positioned_count = serializers.IntegerField(read_only=True)

    def compute_data(self, project):
        return {
            "positioned_collections_count": Collection.objects.filter(project=project, position__isnull=False).count(),
            "positioned_collections_without_exclusion_count": Collection.objects.filter(
                project=project, position=0
            ).count(),
            "collections_remaining_to_be_positioned_count": Collection.objects.filter(
                project=project, position__isnull=True
            ).count(),
        }


class ExclusionInformationSerializer(BaseDashboardMixin, serializers.Serializer):
    excluded_collections_count = serializers.IntegerField(read_only=True)
    excluded_resources_count = serializers.IntegerField(read_only=True)

    def compute_data(self, project):
        return {
            "excluded_collections_count": Collection.objects.filter(project=project, position=0).count(),
            "excluded_resources_count": Resource.objects.filter(
                project=project, status=ResourceStatus.EXCLUDED
            ).count(),
        }


class ArbitrationInformationSerializer(BaseDashboardMixin, serializers.Serializer):
    collections_in_arbitration_0_count = serializers.IntegerField(read_only=True)
    collections_in_arbitration_1_count = serializers.IntegerField(read_only=True)
    resources_with_arbitration_count = serializers.IntegerField(read_only=True)

    def compute_data(self, project):
        return {
            "collections_in_arbitration_0_count": Collection.objects.filter(
                project=project, resource__arbitration=Arbitration.ZERO
            ).count(),
            "collections_in_arbitration_1_count": Collection.objects.filter(
                project=project, resource__arbitration=Arbitration.ONE
            ).count(),
            "resources_with_arbitration_count": Resource.objects.filter(
                project=project, arbitration__in=[Arbitration.ZERO, Arbitration.ONE]
            ).count(),
        }


class InstructionCandidatesInformationSerializer(BaseDashboardMixin, serializers.Serializer):
    collections_candidates_for_instruction_count = serializers.IntegerField(read_only=True)
    resources_candidates_for_instruction_count = serializers.IntegerField(read_only=True)

    duplicates_in_ressource_count = serializers.IntegerField(read_only=True)
    duplicates_in_ressource_ratio = serializers.FloatField(read_only=True)

    triplicates_in_ressource_count = serializers.IntegerField(read_only=True)
    triplicates_in_ressource_ratio = serializers.FloatField(read_only=True)

    quadruplicates_in_ressource_count = serializers.IntegerField(read_only=True)
    quadruplicates_in_ressource_ratio = serializers.FloatField(read_only=True)

    other_higher_multiplicates_in_ressource_count = serializers.IntegerField(read_only=True)
    other_higher_multiplicates_in_ressource_ratio = serializers.FloatField(read_only=True)

    def compute_data(self, project):
        # Resources candidates
        # Conditions: statut < EXCLUDED, arbitrage = NONE, et toutes les collections ont une position.
        candidate_resources = Resource.objects.filter(
            project=project,
            status__lt=ResourceStatus.EXCLUDED,
            arbitration=Arbitration.NONE,
        ).exclude(collections__position__isnull=True)

        # Compter les collections candidates
        # Enlever les collections dont la position est nulle (exclues)
        candidate_collections = Collection.objects.filter(resource__in=candidate_resources).exclude(position=0)

        # 3. Grouper les collections candidates par le 'code' de leur ressource et compter les occurrences.
        code_qs = (
            candidate_collections.values("resource__code")
            # transformer la requête en groupes clé/valeur basés sur le champ resource__code:
            # exemple: [{"resource__code": "ABC123", "count": 3}, {"resource__code": "XYZ000", "count": 2}]
            .annotate(count=Count("id"))
            .filter(count__gt=1)
        )

        # 4. Calculer le nombre total de collections pour chaque niveau de multiplicité.
        duplicates_count = code_qs.filter(count=2).count()
        triplicates_count = code_qs.filter(count=3).count()
        quadruplicates_count = code_qs.filter(count=4).count()
        other_higher_multiplicates_count = code_qs.filter(count__gt=4).count()

        total_resources_count = candidate_resources.count()
        collections_count = candidate_collections.count()

        def calculate_ratio(count, total):
            if total == 0:
                return 0.0
            return round((count / total) * 100, 1)

        return {
            "collections_candidates_for_instruction_count": collections_count,
            "resources_candidates_for_instruction_count": total_resources_count,
            "duplicates_in_ressource_count": duplicates_count,
            "duplicates_in_ressource_ratio": calculate_ratio(duplicates_count, total_resources_count),
            "triplicates_in_ressource_count": triplicates_count,
            "triplicates_in_ressource_ratio": calculate_ratio(triplicates_count, total_resources_count),
            "quadruplicates_in_ressource_count": quadruplicates_count,
            "quadruplicates_in_ressource_ratio": calculate_ratio(quadruplicates_count, total_resources_count),
            "other_higher_multiplicates_in_ressource_count": other_higher_multiplicates_count,
            "other_higher_multiplicates_in_ressource_ratio": calculate_ratio(
                other_higher_multiplicates_count, total_resources_count
            ),
        }


class InstructionsInformationSerializer(BaseDashboardMixin, serializers.Serializer):
    ressources_with_status_instruction_bound_count = serializers.IntegerField(read_only=True)
    ressources_with_status_instruction_unbound_count = serializers.IntegerField(read_only=True)
    ressources_with_instruction_completed_count = serializers.IntegerField(read_only=True)

    def compute_data(self, project):
        return {
            "ressources_with_status_instruction_bound_count": Resource.objects.filter(
                project=project,
                status=ResourceStatus.INSTRUCTION_BOUND,
            ).count(),
            "ressources_with_status_instruction_unbound_count": Resource.objects.filter(
                project=project,
                status=ResourceStatus.INSTRUCTION_UNBOUND,
            ).count(),
            "ressources_with_instruction_completed_count": Resource.objects.filter(
                project=project,
                status=ResourceStatus.EDITION,
            ).count(),
        }


class ControlsInformationSerializer(BaseDashboardMixin, serializers.Serializer):
    ressources_with_bound_copies_being_controlled_count = serializers.IntegerField(read_only=True)
    ressources_with_unbound_copies_being_controlled_count = serializers.IntegerField(read_only=True)

    def compute_data(self, project):
        return {
            "ressources_with_bound_copies_being_controlled_count": Resource.objects.filter(
                project=project,
                status=ResourceStatus.CONTROL_BOUND,
            ).count(),
            "ressources_with_unbound_copies_being_controlled_count": Resource.objects.filter(
                project=project,
                status=ResourceStatus.CONTROL_UNBOUND,
            ).count(),
        }


class AnomaliesInformationSerializer(BaseDashboardMixin, serializers.Serializer):
    anomalies_in_progress_count = serializers.IntegerField(read_only=True)

    def compute_data(self, project):
        anomalies_in_progress_count = Anomaly.objects.filter(
            segment__project=project,
            fixed=False,
        ).count()

        return {
            "anomalies_in_progress_count": anomalies_in_progress_count,
        }


class AchievementsInformationSerializer(BaseDashboardMixin, serializers.Serializer):
    relative_completion = serializers.FloatField(read_only=True)
    absolute_completion = serializers.FloatField(read_only=True)

    def compute_data(self, project):
        # comptages
        processed_resources = Resource.objects.filter(
            project=project,
            status=ResourceStatus.EDITION,
        ).count()

        candidate_qs = Resource.objects.filter(
            project=project,
            status__lt=ResourceStatus.EXCLUDED,
            arbitration=Arbitration.NONE,
        ).exclude(collections__position__isnull=True)

        excluded_resources_count = Resource.objects.filter(
            project=project,
            status=ResourceStatus.EXCLUDED,
        ).count()

        resources_no_longer_to_be_processed = processed_resources + excluded_resources_count
        initial_resources_count = Resource.objects.filter(project=project).count()

        candidate_count = candidate_qs.count()
        relative = round((processed_resources / candidate_count) * 100, 2) if candidate_count > 0 else 0.0
        absolute = (
            round((resources_no_longer_to_be_processed / initial_resources_count) * 100, 2)
            if initial_resources_count > 0
            else 0.0
        )

        return {
            "relative_completion": relative,
            "absolute_completion": absolute,
        }
