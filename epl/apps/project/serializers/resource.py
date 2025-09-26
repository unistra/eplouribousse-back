from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from epl.apps.project.models import Collection, Resource, ResourceStatus
from epl.apps.project.models.collection import TurnType
from epl.apps.project.serializers.collection import CollectionPositioningSerializer
from epl.apps.user.models import User
from epl.libs.schema import load_json_schema
from epl.services.permissions.serializers import AclField, AclSerializerMixin


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
            elif self.instance.status == ResourceStatus.CONTROL_UNBOUND:
                self.instance.status = ResourceStatus.EDITION
            self.instance.save(update_fields=["status"])

        return self.instance
