from rest_framework import serializers

from epl.apps.project.models import Segment


class SegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Segment
        fields = [
            "id",
            "segment_type",
            "content",
            "improvable_elements",
            "exception",
            "improved_segment",
            "collection",
            "order",
            "retained",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "segment_type", "order", "retained", "created_at", "created_by"]
