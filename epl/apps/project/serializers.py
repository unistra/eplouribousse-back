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
    def get_users_with_roles_for_project(cls, project):
        """
        Helper method to get all users with their roles for a given project.
        Returns a list of serialized user data.
        """
        # Get all user roles for this project
        user_roles = UserRole.objects.filter(project=project)

        # Group roles by user
        users_with_roles = {}
        for user_role in user_roles:
            if user_role.user_id not in users_with_roles:
                users_with_roles[user_role.user_id] = {"user": user_role.user, "roles": []}
            users_with_roles[user_role.user_id]["roles"].append(user_role.role)

        # Create a list of user objects with their roles
        users_data = []
        for user_id, data in users_with_roles.items():
            user_obj = data["user"]
            user_obj.roles = data["roles"]
            users_data.append(user_obj)

        # Return serialized data
        return cls(users_data, many=True).data


class UserRoleSerializer(serializers.Serializer):
    role = serializers.CharField(help_text=_("Role"))
    label = serializers.CharField(help_text=_("Role label"))
