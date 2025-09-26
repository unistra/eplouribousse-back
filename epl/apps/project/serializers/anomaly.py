from rest_framework import serializers

from epl.apps.project.models import Anomaly
from epl.apps.project.serializers.segment import NestedSegmentSerializer
from epl.apps.user.serializers import NestedUserSerializer


class AnomalySerializer(serializers.ModelSerializer):
    segment = NestedSegmentSerializer(read_only=True)
    fixed_by = NestedUserSerializer(read_only=True)
    created_by = NestedUserSerializer(read_only=True)

    class Meta:
        model = Anomaly
        fields = [
            "id",
            "segment",
            "type",
            "description",
            "fixed",
            "fixed_at",
            "fixed_by",
            "created_at",
            "created_by",
        ]
        read_only_fields = [
            "id",
            "segment",
            "fixed_by",
            "created_at",
            "created_by",
        ]
