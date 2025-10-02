from django.db import transaction
from django.db.models import F
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import NotFound, ValidationError

from epl.apps.project.models import ResourceStatus, Segment
from epl.apps.project.models.choices import SegmentType
from epl.services.permissions.serializers import AclField, AclSerializerMixin


class NestedSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Segment
        fields = [
            "id",
            "segment_type",
            "content",
            "order",
        ]


class SegmentSerializer(AclSerializerMixin, serializers.ModelSerializer):
    acl = AclField(exclude=["retrieve", "update"])
    after_segment = serializers.UUIDField(required=False, write_only=True)
    anomalies = serializers.SerializerMethodField()

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
            "after_segment",
            "anomalies",
            "acl",
        ]
        read_only_fields = [
            "id",
            "segment_type",
            "order",
            "retained",
            "acl",
            "anomalies",
            "created_by",
            "created_at",
        ]

    @extend_schema_field(
        inline_serializer(
            "NestedAnomaliesSerializer",
            fields={
                "fixed": serializers.IntegerField(help_text=_("Number of fixed anomalies")),
                "unfixed": serializers.IntegerField(help_text=_("Number of unfixed anomalies")),
            },
        )
    )
    def get_anomalies(self, obj):
        return {
            "fixed": obj.fixed_anomalies,
            "unfixed": obj.unfixed_anomalies,
        }

    def create(self, validated_data):
        after_segment_id = validated_data.pop("after_segment", None)
        collection = validated_data["collection"]
        resource = collection.resource

        with transaction.atomic():
            if after_segment_id:
                try:
                    after_segment = Segment.objects.get(id=after_segment_id)

                    new_order = after_segment.order + 1

                    Segment.objects.filter(collection__resource=resource, order__gte=new_order).update(
                        order=F("order") + 1
                    )
                except Segment.DoesNotExist:
                    raise NotFound(_("Referenced segment does not exist"))
            else:
                new_order = Segment.get_last_order(resource)

            segment_type = (
                SegmentType.BOUND if resource.status <= ResourceStatus.INSTRUCTION_BOUND else SegmentType.UNBOUND
            )

            # Create the segment with the calculated order
            instance = Segment.objects.create(
                **validated_data,
                segment_type=segment_type,
                order=new_order,
                retained=False,
                created_by=self.context["request"].user,
                created_at=now(),
            )

            return instance


class SegmentOrderSerializer(serializers.Serializer):
    current_segment = serializers.SerializerMethodField()
    previous_segment = serializers.SerializerMethodField()
    next_segment = serializers.SerializerMethodField()

    def get_current_segment(self, obj):
        current = obj.get("current")
        if current:
            return {"id": str(current.id), "order": current.order}
        return None

    def get_previous_segment(self, obj):
        previous = obj.get("previous")
        if previous:
            return {"id": str(previous.id), "order": previous.order}
        return None

    def get_next_segment(self, obj):
        next_seg = obj.get("next")
        if next_seg:
            return {"id": str(next_seg.id), "order": next_seg.order}
        return None

    def move_up(self, segment):
        resource = segment.collection.resource
        current_order = segment.order

        if current_order <= 1:
            raise ValidationError(_("Segment is already at the top of the collection"))

        try:
            previous_segment = Segment.objects.get(collection__resource=resource, order=current_order - 1)
        except Segment.DoesNotExist:
            raise NotFound(_("Previous segment not found"))

        with transaction.atomic():
            segment.order, previous_segment.order = previous_segment.order, segment.order
            segment.save(update_fields=["order"])
            previous_segment.save(update_fields=["order"])

        return {"current": segment, "previous": previous_segment}

    def move_down(self, segment):
        resource = segment.collection.resource
        current_order = segment.order

        try:
            next_segment = Segment.objects.get(collection__resource=resource, order=current_order + 1)
        except Segment.DoesNotExist:
            raise ValidationError(_("Segment is already at the bottom of the collection"))

        with transaction.atomic():
            segment.order, next_segment.order = next_segment.order, segment.order
            segment.save(update_fields=["order"])
            next_segment.save(update_fields=["order"])

        return {"current": segment, "next": next_segment}
