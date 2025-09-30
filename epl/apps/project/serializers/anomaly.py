from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from epl.apps.project.models import Anomaly, AnomalyType
from epl.apps.project.serializers.segment import NestedSegmentSerializer
from epl.apps.user.serializers import NestedUserSerializer


class AnomalySerializer(serializers.ModelSerializer):
    segment = NestedSegmentSerializer(read_only=True)
    segment_id = serializers.UUIDField(write_only=True)
    description = serializers.CharField(
        allow_blank=True,
        required=False,
        help_text=_("Description (required if type is 'Other')"),
    )
    fixed_by = NestedUserSerializer(read_only=True, help_text=_("The user who fixed the anomaly"))
    created_by = NestedUserSerializer(read_only=True, help_text=_("The user who created the anomaly"))

    class Meta:
        model = Anomaly
        fields = [
            "id",
            "segment",
            "segment_id",
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
            "fixed_at",
            "created_at",
            "created_by",
        ]
        write_only_fields = [
            "segment_id",
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get("type") == AnomalyType.OTHER and not attrs["description"].strip():
            raise serializers.ValidationError({"description": _("Description is required for 'Other' anomaly type.")})
        return attrs

    def validate_segment_id(self, value):
        from epl.apps.project.models import Segment

        try:
            segment = Segment.objects.get(id=value)
        except Segment.DoesNotExist:
            raise serializers.ValidationError(_("Segment with the given ID does not exist."))
        return segment

    def create(self, validated_data):
        segment = validated_data.pop("segment_id")
        resource = segment.collection.resource
        user = self.context["request"].user

        anomaly = Anomaly.objects.create(
            segment=segment,
            resource=resource,
            created_by=user,
            **validated_data,
        )
        return anomaly
