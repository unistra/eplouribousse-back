from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from epl.apps.project.models import Project, Role, UserRole
from epl.apps.user.models import User


class ProjectSerializer(serializers.ModelSerializer):
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


class AssignRoleSerializer(serializers.Serializer):
    role = serializers.CharField(help_text=_("Role"))
    user = serializers.UUIDField(help_text=_("User id"))

    def validate_role(self, role):
        if role not in Role.values:
            raise serializers.ValidationError(_("Invalid role."))
        return role

    def validate_user(self, user):
        try:
            user = User.objects.active().get(pk=user)
        except User.DoesNotExist:
            raise serializers.ValidationError(_("User does not exist."))
        return user.id

    def save(self):
        if self.context["request"].method == "POST":
            return UserRole.objects.get_or_create(
                user=self.validated_data["user"],
                role=self.validated_data["role"],
                project=self.context["project"],
            )
        elif self.context["request"].method == "DELETE":
            result = UserRole.objects.filter(
                user=self.validated_data["user"],
                role=self.validated_data["role"],
                project=self.context["project"],
            ).delete()
            if not result[0]:
                raise serializers.ValidationError(_("Role not found for this user in the project."))
        return None
