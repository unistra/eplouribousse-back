from rest_framework import serializers

from epl.apps.project.models import ProjectLibrary


class ProjectLibraryAlternativeStorageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectLibrary
        fields = ["is_alternative_storage_site"]


class ProjectLibraryPatchSerializer(serializers.Serializer):
    is_alternative_storage_site = serializers.BooleanField()
