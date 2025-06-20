from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from epl.apps.project.models import Project, Role, UserRole
from epl.apps.project.models.library import Library
from epl.apps.user.models import User


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name", "description", "invitations", "created_at", "updated_at"]
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
    role = serializers.ChoiceField(choices=Role.choices)
    label = serializers.CharField(help_text=_("Role label"))


class AssignRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.choices)
    user_id = serializers.UUIDField(help_text=_("User id"))
    library_id = serializers.UUIDField(help_text=_("Library id"), required=False)

    def validate_user(self, user_id):
        try:
            user = User.objects.active().get(pk=user_id)
        except User.DoesNotExist:
            raise serializers.ValidationError(_("User does not exist."))
        return user.id

    def validate_library(self, library_id):
        try:
            library = Library.objects.get(pk=library_id)
        except Library.DoesNotExist:
            raise serializers.ValidationError(_("Library does not exist."))
        return library.id

    def save(self):
        if self.context["request"].method == "POST":
            return UserRole.objects.get_or_create(
                user_id=self.validated_data["user_id"],
                role=self.validated_data["role"],
                library_id=self.validated_data.get(
                    "library_id"
                ),  # get method is used to avoid KeyError if library_id is not provided
                project=self.context["project"],
            )
        elif self.context["request"].method == "DELETE":
            result = UserRole.objects.filter(
                user_id=self.validated_data["user_id"],
                role=self.validated_data["role"],
                library_id=self.validated_data.get("library_id"),
                project=self.context["project"],
            ).delete()
            if not result[0]:
                raise serializers.ValidationError(_("Role not found for this user in the project."))
        return None


class InvitationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Role.choices)
    library = serializers.CharField(
        required=False, allow_null=True
    )  # UUID as string, to avoid useless complexity of UUIDField in JSON


class ProjectInvitationsSerializer(serializers.Serializer):
    invitations = InvitationSerializer(many=True)

    def save(self):
        project = self.context["project"]
        project.invitations = self.validated_data["invitations"]
        project.save()
