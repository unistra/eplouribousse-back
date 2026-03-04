from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


class NestedAnomalySerializer(serializers.Serializer):
    fixed = serializers.IntegerField(help_text=_("Number of fixed anomalies"))
    unfixed = serializers.IntegerField(help_text=_("Number of unfixed anomalies"))
