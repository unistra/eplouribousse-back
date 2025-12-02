from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


class StatusListSerializer(serializers.Serializer):
    status = serializers.IntegerField(help_text=_("Project status"))
    label = serializers.CharField(help_text=_("Label"))
