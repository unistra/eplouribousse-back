from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from epl.apps.project.models import Resource
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

    class Meta:
        model = Resource
        fields = ["id", "title", "code", "count", "call_numbers", "should_instruct", "status", "arbitration", "acl"]

    def get_should_instruct(self, obj: Resource) -> bool:
        library_id = obj.next_turn
        user: User = self.context.get("request").user

        if not user or not user.is_authenticated or not library_id:
            return False
        return user.is_instructor(obj.project, library_id)


class ResourceWithCollectionsSerializer(serializers.Serializer):
    resource = ResourceSerializer()
    collections = CollectionPositioningSerializer(many=True)
