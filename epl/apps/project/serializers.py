from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from epl.apps.project.models import Project
from epl.apps.user.models import User


class ProjectSerializer(serializers.ModelSerializer):
    """Serializer for the Project model"""

    class Meta:
        model = Project
        fields = ["id", "name", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProjectUserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField(
        help_text=_("User's roles in this project"),
    )

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "roles"]
        read_only_fields = fields

    def get_roles(self, instance) -> list[str]:
        return [role.role for role in instance.project_roles.all()]


class UserRoleSerializer(serializers.Serializer):
    role = serializers.CharField(help_text=_("Role"))
    label = serializers.CharField(help_text=_("Role label"))
