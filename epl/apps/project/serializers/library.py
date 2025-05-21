from rest_framework import serializers

from epl.apps.project.models.library import Library


class LibrairySerializer(serializers.ModelSerializer):
    """
    Serializer for Librairy model.
    """

    class Meta:
        model = Library
        fields = ["id", "name", "alias", "code", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
