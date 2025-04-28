from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from .models import Consortium


class ConsortiumSerializer(ModelSerializer):
    """
    This Serializer is used to perform GET operations consortium objects.
    """

    settings = serializers.JSONField(source="tenant_settings")

    class Meta:
        model = Consortium
        fields = ["id", "name", "settings"]
