from rest_framework.serializers import ModelSerializer

from .models import Consortium


class ConsortiumSerializer(ModelSerializer):
    """
    This Serializer is used to perform GET operations consortium objects.
    """

    class Meta:
        model = Consortium
        fields = ["id", "name", "tenant_settings"]
