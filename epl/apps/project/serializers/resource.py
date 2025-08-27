from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from epl.apps.project.models import Collection, Resource
from epl.apps.project.serializers.collection import CollectionPositioningSerializer
from epl.apps.user.models import User
from epl.services.permissions.serializers import AclField, AclSerializerMixin


class ResourceSerializer(AclSerializerMixin, serializers.ModelSerializer):
    acl = AclField()
    count = serializers.IntegerField(read_only=True)
    call_numbers = serializers.CharField(read_only=True)
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
            "should_position",
            "status",
            "arbitration",
            "acl",
        ]

    def get_should_instruct(self, obj: Resource) -> bool:
        library_id = obj.next_turn
        user: User = self.context.get("request").user

        if not user or not user.is_authenticated or not library_id:
            return False
        return user.is_instructor(obj.project, library_id)

    def get_should_position(self, obj: Resource) -> bool:
        user: User = self.context.get("request").user
        library_id_selected = self.context.get("library")

        if library_id_selected and user.is_instructor(project=obj.project, library=library_id_selected):
            return Collection.objects.filter(
                resource=obj, library_id=library_id_selected, position=None, exclusion_reason__in=["", None]
            ).exists()

        return False


class ResourceWithCollectionsSerializer(serializers.Serializer):
    resource = ResourceSerializer()
    collections = CollectionPositioningSerializer(many=True)
