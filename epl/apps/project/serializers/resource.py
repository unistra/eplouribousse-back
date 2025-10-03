from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers

from epl.apps.project.models import Collection, Resource, ResourceStatus
from epl.apps.project.models.collection import TurnType
from epl.apps.project.serializers.collection import CollectionPositioningSerializer
from epl.apps.user.models import User
from epl.libs.schema import load_json_schema
from epl.services.permissions.serializers import AclField, AclSerializerMixin
from epl.services.project.notifications import notify_instructors_of_instruction_turn


@extend_schema_field(load_json_schema("resource_instruction_turns.schema.json"))
class InstructionTurnsField(serializers.JSONField): ...


class ResourceSerializer(AclSerializerMixin, serializers.ModelSerializer):
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
            "should_instruct",
            "instruction_turns",
            "should_position",
            "status",
            "arbitration",
            "anomalies",
            "acl",
        ]

    def get_should_instruct(self, obj: Resource) -> bool:
        next_turn: TurnType | None = obj.next_turn
        library_id = next_turn["library"] if next_turn else None
        user: User = self.context.get("request").user

        if not user or not user.is_authenticated or not library_id:
            return False
        return user.is_instructor(obj.project, library_id)

    def get_should_position(self, obj: Resource) -> bool:
        user: User = self.context.get("request").user
        library_id_selected = self.context.get("library")

        if (
            library_id_selected
            and user.is_authenticated
            and user.is_instructor(project=obj.project, library=library_id_selected)
        ):
            return Collection.objects.filter(
                resource=obj, library_id=library_id_selected, position=None, exclusion_reason__in=["", None]
            ).exists()

        return False

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
                library_id = self.instance.next_turn["library"] if self.instance.next_turn else None
                collection = Collection.objects.get(library_id=library_id, resource=self.instance)
                notify_instructors_of_instruction_turn(self.instance, collection, self.context["request"])
            elif self.instance.status == ResourceStatus.CONTROL_UNBOUND:
                self.instance.status = ResourceStatus.EDITION
                # todo send email to all instructors (notify them that a resulting report is available)
                # https://gitlab.unistra.fr/di/eplouribousse/eplouribousse/-/issues/22
                # https://gitlab.unistra.fr/di/eplouribousse/eplouribousse/-/issues/80

            self.instance.save(update_fields=["status"])

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
        # 2 Send notifications TODO
        return self.instance
