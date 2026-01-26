from django.utils import timezone
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers

from epl.apps.project.models import ActionLog, Anomaly, Collection, Library, Resource, ResourceStatus, Segment
from epl.apps.project.models.choices import SegmentType
from epl.apps.project.serializers.collection import CollectionPositioningSerializer
from epl.apps.project.serializers.mixins import ResourceInstructionMixin
from epl.libs.schema import load_json_schema
from epl.services.permissions.serializers import AclField, AclSerializerMixin
from epl.services.project.notifications import (
    notify_anomaly_reported,
    notify_anomaly_resolved,
    notify_instructors_of_instruction_turn,
    notify_resultant_report_available,
)


@extend_schema_field(load_json_schema("resource_instruction_turns.schema.json"))
class InstructionTurnsField(serializers.JSONField): ...


class ResourceSerializer(AclSerializerMixin, ResourceInstructionMixin, serializers.ModelSerializer):
    acl = AclField()
    count = serializers.IntegerField(read_only=True)
    call_numbers = serializers.CharField(read_only=True)
    instruction_turns = InstructionTurnsField(read_only=True)

    should_instruct = serializers.SerializerMethodField(
        read_only=True, help_text=_("Indicates if the user should instruct this resource")
    )
    should_position = serializers.SerializerMethodField(
        read_only=True, help_text=_("Indicates if the user should position this resource")
    )
    anomalies = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Resource
        fields = [
            "id",
            "title",
            "code",
            "count",
            "call_numbers",
            "issn",
            "publication_history",
            "numbering",
            "should_instruct",
            "instruction_turns",
            "should_position",
            "status",
            "arbitration",
            "anomalies",
            "validations",
            "acl",
        ]

    def to_representation(self, instance):
        # In this particular case, resources don't have anomalies counts
        # only the collections have them
        representation = super().to_representation(instance)
        if self.context.get("hide_anomalies"):
            representation.pop("anomalies", None)
        return representation

    @extend_schema_field(
        inline_serializer(
            "NestedAnomaliesSerializer",
            fields={
                "fixed": serializers.IntegerField(help_text=_("Number of fixed anomalies")),
                "unfixed": serializers.IntegerField(help_text=_("Number of unfixed anomalies")),
            },
        )
    )
    def get_anomalies(self, obj: Resource) -> dict[str, int]:
        return {
            "fixed": getattr(obj, "fixed_anomalies", 0) or 0,
            "unfixed": getattr(obj, "unfixed_anomalies", 0) or 0,
        }


class ResourceWithCollectionsSerializer(serializers.Serializer):
    resource = ResourceSerializer()
    collections = CollectionPositioningSerializer(many=True)


class ValidateControlSerializer(serializers.ModelSerializer):
    validation = serializers.BooleanField(
        write_only=True, help_text=_("Indicates if the controller validates the instruction phase")
    )
    status = serializers.CharField(read_only=True, help_text=_("The new status of the resource after validation"))
    instruction_turns = InstructionTurnsField(
        read_only=True, help_text=_("The updated instruction turns of the resource after validation")
    )

    class Meta:
        model = Resource
        fields = [
            "id",
            "validation",
            "status",
            "instruction_turns",
        ]
        read_only_fields = [
            "id",
            "status",
            "instruction_turns",
        ]

    def validate(self, attrs):
        if self.instance.status not in [ResourceStatus.CONTROL_BOUND, ResourceStatus.CONTROL_UNBOUND]:
            raise serializers.ValidationError(
                {
                    "status": _("The resource is not in control status"),
                }
            )
        return super().validate(attrs)

    def save(self, **kwargs) -> Resource:
        if self.validated_data.get("validation"):
            # The controller validates the instruction phase
            if self.instance.status == ResourceStatus.CONTROL_BOUND:
                self.instance.status = ResourceStatus.INSTRUCTION_UNBOUND
                turn = self.instance.next_turn
                library = Library.objects.get(id=turn["library"])
                self.instance.validations["control_bound"] = now().isoformat()
                notify_instructors_of_instruction_turn(self.instance, library, self.context["request"])
                ActionLog.log(
                    f"{ResourceStatus(ResourceStatus.CONTROL_BOUND).name} validated: unbound instruction turn notified to <lib:{turn['library']}/col:{turn['collection']}>",
                    actor=self.context["request"].user,
                    obj=self.instance,
                    request=self.context.get("request"),
                )
            elif self.instance.status == ResourceStatus.CONTROL_UNBOUND:
                self.instance.validations["control_unbound"] = now().isoformat()
                self.instance.status = ResourceStatus.EDITION
                notify_resultant_report_available(self.instance, self.context["request"])
                ActionLog.log(
                    f"{ResourceStatus(ResourceStatus.CONTROL_UNBOUND).name} validated: resource moved to EDITION",
                    actor=self.context["request"].user,
                    obj=self.instance,
                    request=self.context.get("request"),
                )

            self.instance.save(update_fields=["status", "validations"])

        return self.instance


class ReportAnomaliesSerializer(serializers.ModelSerializer):
    instruction_turns = InstructionTurnsField(
        read_only=True, help_text=_("The updated instruction turns of the resource")
    )

    class Meta:
        model = Resource
        fields = ["id", "status", "instruction_turns"]
        read_only_fields = ["id", "status", "instruction_turns"]

    def report(self):
        # 1 Change status to ANOMALY
        match self.instance.status:
            case ResourceStatus.INSTRUCTION_BOUND | ResourceStatus.CONTROL_BOUND:
                self.instance.status = ResourceStatus.ANOMALY_BOUND
            case ResourceStatus.INSTRUCTION_UNBOUND | ResourceStatus.CONTROL_UNBOUND:
                self.instance.status = ResourceStatus.ANOMALY_UNBOUND
            case _:
                raise serializers.ValidationError(
                    {
                        "status": _("The resource is not in instruction or control status"),
                    }
                )
        self.instance.save(update_fields=["status"])

        # 2 Get all active anomalies of the resource
        anomalies = (
            self.instance.anomalies.filter(fixed=False)
            .select_related("segment__collection__library")
            .order_by("-created_at")
        )

        # 3 Send notifications
        notify_anomaly_reported(
            self.instance, self.context["request"], self.context["request"].user, anomalies=list(anomalies)
        )

        return self.instance


class ResetInstructionSerializer(serializers.ModelSerializer):
    instruction_turns = InstructionTurnsField(
        read_only=True, help_text=_("The updated instruction turns of the resource after reset")
    )

    class Meta:
        model = Resource
        fields = [
            "id",
            "status",
            "instruction_turns",
        ]
        read_only_fields = [
            "id",
            "status",
            "instruction_turns",
        ]

    def reset(self) -> Resource:
        collections = self.instance.collections.all()

        match self.instance.status:
            case ResourceStatus.ANOMALY_BOUND:
                Segment.objects.filter(collection__in=collections).delete()
                self.instance.status = ResourceStatus.INSTRUCTION_BOUND
                self.instance.instruction_turns["bound_copies"]["turns"] = self.instance.calculate_turns()
            case ResourceStatus.ANOMALY_UNBOUND:
                Segment.objects.filter(collection__in=collections, segment_type=SegmentType.UNBOUND).delete()
                self.instance.status = ResourceStatus.INSTRUCTION_UNBOUND
                self.instance.instruction_turns["unbound_copies"]["turns"] = self.instance.calculate_turns()
            case _:
                raise serializers.ValidationError(
                    {
                        "status": _("The resource is not in anomaly status"),
                    }
                )

        self.instance.save(update_fields=["status", "instruction_turns"])
        ActionLog.log(
            f"Resource in {ResourceStatus(self.instance.status).name}: instruction reset",
            actor=self.context["request"].user,
            obj=self.instance,
            request=self.context.get("request"),
        )
        # There is no need to delete anomalies, they are deleted with the segments
        notify_anomaly_resolved(
            resource=self.instance, request=self.context["request"], admin_user=self.context["request"].user
        )
        return self.instance


class ReassignInstructionTurnSerializer(serializers.ModelSerializer):
    instruction_turns = InstructionTurnsField(
        read_only=True, help_text=_("The updated instruction turns of the resource after reassigning turns")
    )
    collection_id = serializers.UUIDField(
        write_only=True,
        help_text=_("The collection id to which the instruction turn will be reassigned"),
        required=False,
    )
    library_id = serializers.UUIDField(
        write_only=True,
        help_text=_("The library id to which the instruction turn will be reassigned"),
        required=False,
    )
    controller = serializers.BooleanField(
        write_only=True,
        help_text=_("Indicates if the turn is reassigned to a controller"),
        default=False,
    )

    class Meta:
        model = Resource
        fields = [
            "id",
            "status",
            "instruction_turns",
            "collection_id",
            "library_id",
            "controller",
        ]
        read_only_fields = [
            "id",
            "status",
            "instruction_turns",
        ]

    def validate_collection_id(self, value):
        try:
            collection = Collection.objects.get(id=value)
        except Collection.DoesNotExist:
            raise serializers.ValidationError(_("Collection does not exist"))

        if str(collection.id) not in [
            _turn["collection"] for _turn in self.instance.instruction_turns.get("turns", [])
        ]:
            raise serializers.ValidationError(_("Collection is not in the instruction turns of the resource"))
        return collection

    def validate_library_id(self, value):
        try:
            library = Library.objects.get(id=value)
        except Library.DoesNotExist:
            raise serializers.ValidationError(_("Library does not exist"))

        if str(library.id) not in [_turn["library"] for _turn in self.instance.instruction_turns.get("turns", [])]:
            raise serializers.ValidationError(_("Library is not in the instruction turns of the resource"))
        return library

    def validate(self, attrs: dict) -> dict:
        if self.instance.status not in [ResourceStatus.ANOMALY_BOUND, ResourceStatus.ANOMALY_UNBOUND]:
            raise serializers.ValidationError(
                {
                    "status": _("The resource is not in anomaly status"),
                }
            )
        if attrs.get("controller"):
            # collection_id and library_id should not be provided
            if "collection_id" in attrs or "library_id" in attrs:
                raise serializers.ValidationError(
                    {
                        "non_field_errors": _(
                            "When reassigning to a controller, collection_id and library_id should not be provided"
                        ),
                    }
                )
        else:
            # collection_id and library_id must be provided
            if not attrs.get("collection_id") or not attrs.get("library_id"):
                raise serializers.ValidationError(
                    {
                        "non_field_errors": _("collection_id and library_id must be provided"),
                    }
                )
        return attrs

    def reassign(self) -> Resource:
        request = self.context["request"]
        if self.validated_data.get("controller"):
            # Reassign to controller
            self.reassign_to_controller()
            ActionLog.log(
                message=f"Resource in {ResourceStatus(self.instance.status).name} (turn reassigned to controller)",
                actor=request.user,
                obj=self.instance,
                request=request,
            )
        else:
            # Reassign to instructor of library/collection
            self.reassign_to_instructor()
            ActionLog.log(
                message=f"Resource in {ResourceStatus(self.instance.status).name} (turn reassigned to instructor <lib:{self.instance.next_turn['library']}/col:{self.instance.next_turn['collection']}>)",
                actor=request.user,
                obj=self.instance,
                request=request,
            )

        self.fix_anomalies()
        notify_anomaly_resolved(
            resource=self.instance, request=self.context["request"], admin_user=self.context["request"].user
        )
        return self.instance

    def fix_anomalies(self):
        Anomaly.objects.filter(resource=self.instance, fixed=False).update(
            fixed=True,
            fixed_at=timezone.now(),
            fixed_by=self.context["request"].user,
        )

    def reassign_to_instructor(self):
        collection: Collection = self.validated_data.get("collection_id")
        library: Library = self.validated_data.get("library_id")

        # iterate over turns, delete those preceding the selected library/collection
        match self.instance.status:
            case ResourceStatus.ANOMALY_BOUND:
                cycle = "bound_copies"
            case ResourceStatus.ANOMALY_UNBOUND:
                cycle = "unbound_copies"
            case _:
                raise serializers.ValidationError(
                    {
                        "status": _("The resource is not in anomaly status"),
                    }
                )

        turns = self.instance.instruction_turns.get("turns", {})
        for idx, turn in enumerate(turns):
            if turn["library"] == str(library.id) and turn["collection"] == str(collection.id):
                break
        self.instance.instruction_turns[cycle]["turns"] = turns[idx:]
        self.instance.status = (
            ResourceStatus.INSTRUCTION_BOUND if cycle == "bound_copies" else ResourceStatus.INSTRUCTION_UNBOUND
        )
        self.instance.save(update_fields=["status", "instruction_turns"])

    def reassign_to_controller(self):
        match self.instance.status:
            case ResourceStatus.ANOMALY_BOUND:
                self.instance.status = ResourceStatus.CONTROL_BOUND
                self.instance.instruction_turns["bound_copies"]["turns"] = []
            case ResourceStatus.ANOMALY_UNBOUND:
                self.instance.status = ResourceStatus.CONTROL_UNBOUND
                self.instance.instruction_turns["unbound_copies"]["turns"] = []
            case _:
                raise serializers.ValidationError(
                    {
                        "status": _("The resource is not in anomaly status"),
                    }
                )
        self.instance.save(update_fields=["status", "instruction_turns"])
