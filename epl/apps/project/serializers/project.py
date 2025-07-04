from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from epl.apps.project.models import Collection, Project, Role, Status, UserRole
from epl.apps.project.models.library import Library
from epl.apps.project.serializers.library import LibrarySerializer
from epl.apps.user.models import User
from epl.apps.user.serializers import NestedUserSerializer


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name", "description", "status", "settings", "created_at", "updated_at"]
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


class NestedUserRoleSerializer(serializers.ModelSerializer):
    user = NestedUserSerializer()
    role = serializers.CharField()

    class Meta:
        model = UserRole
        fields = ["user", "role", "library_id"]


class InvitationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Role.choices)
    library_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_library_id(self, library_id):
        role = self.initial_data.get("role")
        if role is not None and role != Role.INSTRUCTOR:
            raise serializers.ValidationError(_("Library should not be provided for this role."))
        project = self.context["project"]
        if not project.libraries.filter(pk=library_id).exists():
            raise serializers.ValidationError(_("Library is not attached to the project."))
        return str(library_id)

    def validate(self, attrs):
        project = self.context["project"]
        try:
            Project.objects.get(pk=project.pk)
        except Project.DoesNotExist:
            raise serializers.ValidationError(_("Project does not exist."))

        role = self.initial_data.get("role")
        if role == Role.INSTRUCTOR and "library_id" not in self.initial_data:
            raise serializers.ValidationError(_("Library must be provided for instructor role."))
        return attrs

    def save(self):
        if self.context["request"].method == "POST":
            project = self.context["project"]
            invitations = project.invitations or []
            invitation = self.validated_data.copy()

            for inv in invitations:
                if (
                    inv.get("email") == invitation.get("email")
                    and inv.get("role") == invitation.get("role")
                    and inv.get("library_id") == invitation.get("library_id")
                ):
                    raise ValidationError(_("This invitation already exists."))

            invitations.append(invitation)
            project.invitations = invitations
            project.save()

        elif self.context["request"].method == "DELETE":
            project = self.context["project"]
            invitations = project.invitations or []
            invitation = self.validated_data

            for inv in invitations:
                if (
                    inv.get("email") == invitation.get("email")
                    and inv.get("role") == invitation.get("role")
                    and inv.get("library_id") == invitation.get("library_id")
                ):
                    invitations.remove(inv)
                    project.invitations = invitations
                    project.save()
                    return

            raise ValidationError(_("Invitation not found."))

    def clear(self):
        project = self.context["project"]
        project.invitations = []
        project.save()


class ProjectDetailSerializer(serializers.ModelSerializer):
    roles = NestedUserRoleSerializer(many=True, read_only=True, source="user_roles")
    libraries = LibrarySerializer(many=True)
    invitations = InvitationSerializer(many=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "is_private",
            "active_after",
            "status",
            "settings",
            "invitations",
            "roles",
            "libraries",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SetStatusSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=Status.choices, help_text=_("Project status"))

    class Meta:
        model = Project
        fields = ["id", "status"]
        read_only_fields = ["id"]


class StatusListSerializer(serializers.Serializer):
    status = serializers.IntegerField(help_text=_("Project status"))
    label = serializers.CharField(help_text=_("Label"))


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
            user_role, _created = UserRole.objects.filter(
                user_id=self.validated_data["user_id"],
                role=self.validated_data["role"],
                library_id=self.validated_data.get(
                    "library_id"
                ),  # get method is used to avoid KeyError if library_id is not provided
                project=self.context["project"],
            ).get_or_create(
                user_id=self.validated_data["user_id"],
                role=self.validated_data["role"],
                library_id=self.validated_data.get("library_id"),
                project=self.context["project"],
                assigned_by=self.context["request"].user,
            )
            return user_role
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

    def to_representation(self, instance):
        user = User.objects.get(pk=instance.get("user_id"))
        data = {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "firstName": user.first_name,
                "lastName": user.last_name,
            },
            "role": instance.get("role"),
            "libraryId": str(instance.get("library_id")) if instance.get("library_id") else None,
        }
        return data


class ProjectLibrarySerializer(serializers.Serializer):
    library_id = serializers.UUIDField()

    def validate_library_id(self, value):
        if not Library.objects.filter(id=value).exists():
            raise serializers.ValidationError(_("Library does not exist."))

        if self.context["request"].method == "DELETE":
            project = self.context["project"]
            if not project.libraries.filter(id=value).exists():
                raise serializers.ValidationError(_("Library is not attached to the project."))
        return value

    def save(self):
        project = self.context["project"]
        library = Library.objects.get(id=self.validated_data.get("library_id"))
        if self.context["request"].method == "POST":
            if not project.libraries.filter(id=library.id).exists():
                project.libraries.add(library)
        elif self.context["request"].method == "DELETE":
            project.libraries.remove(library)
            UserRole.objects.filter(project_id=project.id, library_id=library.id).delete()
            Collection.objects.filter(project_id=project.id, library_id=library.id).delete()
            project.invitations = [
                inv for inv in (project.invitations or []) if inv.get("library_id") != str(library.id)
            ]
            project.save()
        return None
