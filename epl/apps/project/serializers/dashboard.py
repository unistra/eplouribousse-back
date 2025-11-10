from django.core.cache import cache
from rest_framework import serializers

from epl.apps.project.models.collection import Collection, Resource
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
        if cached_data:
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
            "excluded_resources_count": Resource.objects.filter(project=project, status=15).count(),
        }
