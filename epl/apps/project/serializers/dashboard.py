from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from epl.apps.project.models.collection import Collection, Resource


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

        initial_collections_count = Collection.objects.filter(project=project).count()
        initial_resources_count = Resource.objects.filter(project=project).count()

        return {
            "initial_collections_count": initial_collections_count,
            "initial_resources_count": initial_resources_count,
        }
