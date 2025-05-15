from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from epl.apps.project.models import Project, UserRole
from epl.apps.user.models import User


class ProjectSerializer(serializers.ModelSerializer):
    """Serializer for the Project model"""

    class Meta:
        model = Project
        fields = ["id", "name", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProjectUserSerializer(serializers.ModelSerializer):
    roles = serializers.ListField(
        child=serializers.CharField(), help_text=_("User's roles in this project"), read_only=True
    )  # Tells DRF that roles has to be serialized as a list of strings

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "roles"]
        read_only_fields = fields

    @classmethod
    def get_serialized_users_for_project(cls, project):
        users = UserRole.get_users_with_roles_for_project(project)
        return cls(users, many=True).data


class UserRoleSerializer(serializers.Serializer):
    role = serializers.CharField(help_text=_("Role"))
    label = serializers.CharField(help_text=_("Role label"))
