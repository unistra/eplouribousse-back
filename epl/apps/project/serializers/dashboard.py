from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from epl.apps.project.models.collection import Collection, Resource
from epl.settings import base as base_settings


class ProjectDashboardSerializer(serializers.Serializer):
    """
    Serializer for project dashboard initial data.
    """

    initial_collections_count = serializers.IntegerField(
        help_text=_("Number of initial collections before positioning"),
        read_only=True,
    )
    initial_resources_count = serializers.IntegerField(
        help_text=_("Number of initial resources before positioning"),
        read_only=True,
    )

    def to_representation(self, instance):
        project = instance
        cache_key = f"project_dashboard_{project.id}"

        # check cache
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        # if not cached, calculate and cache

        initial_collections_count = Collection.objects.filter(project=project).count()
        initial_resources_count = Resource.objects.filter(project=project).count()

        data = {
            "initial_collections_count": initial_collections_count,
            "initial_resources_count": initial_resources_count,
        }

        # cach for 3h
        cache.set(cache_key, data, timeout=base_settings.CACHE_TIMEOUT_DASHBOARD)
        return data
