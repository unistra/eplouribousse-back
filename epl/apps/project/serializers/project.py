from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from epl.apps.project.models import (
    ActionLog,
    Collection,
    Library,
    Project,
    ProjectLibrary,
    ProjectStatus,
    Role,
    UserRole,
)
from epl.apps.user.models import User
from epl.apps.user.serializers import NestedUserSerializer
from epl.libs.schema import load_json_schema
from epl.services.permissions.serializers import AclField, AclSerializerMixin
from epl.services.project.notifications import (
    invite_project_admins_to_review,
    invite_project_managers_to_launch,
    invite_single_user_to_epl,
    invite_unregistered_users_to_epl,
    notify_project_launched,
)
from epl.services.user.email import (
    send_invite_project_admins_to_review_email,
    send_invite_project_managers_to_launch_email,
    send_project_launched_email,
)
from epl.validators import JSONSchemaValidator


@extend_schema_field(load_json_schema("project_settings.schema.json"))
class ProjectSettingsField(serializers.JSONField): ...


class ProjectSerializer(AclSerializerMixin, serializers.ModelSerializer):
    acl = AclField()
    settings = ProjectSettingsField(
        required=False,
        help_text=_("Project settings"),
        validators=[JSONSchemaValidator("project_settings.schema.json")],
    )

    class Meta:
        model = Project
        fields = ["id", "name", "description", "status", "is_active", "settings", "created_at", "updated_at", "acl"]
        read_only_fields = ["id", "is_active", "created_at", "updated_at"]


class CreateProjectSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    settings = ProjectSettingsField(
        required=False,
        help_text=_("Project settings"),
        validators=[JSONSchemaValidator("project_settings.schema.json")],
    )

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "settings",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def save(self):
        project = super().save()

        project_creator = self.context["request"].user
        current_settings = project.settings or {}
        current_settings["project_creator"] = str(project_creator.username)
        project.settings = current_settings
        project.save(update_fields=["settings"])

        ActionLog.log(f"Project <{project.name}> created", project_creator, obj=project)

        return project


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

            # If the project status > DRAFT, send an invitation email to the user.
            # (as the invitations are fired when the project.status switches from DRAFT to REVIEW)
            if project.status > ProjectStatus.DRAFT:
                invite_single_user_to_epl(project, invitation, self.context["request"])

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


class ProjectLibraryDetailSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="library.id")
    name = serializers.CharField(source="library.name")
    alias = serializers.CharField(source="library.alias")
    code = serializers.CharField(source="library.code")
    created_at = serializers.DateTimeField(source="library.created_at")
    updated_at = serializers.DateTimeField(source="library.updated_at")

    class Meta:
        model = ProjectLibrary
        fields = [
            "id",
            "name",
            "alias",
            "code",
            "created_at",
            "updated_at",
            "is_alternative_storage_site",
        ]


class ProjectDetailSerializer(AclSerializerMixin, serializers.ModelSerializer):
    roles = NestedUserRoleSerializer(many=True, read_only=True, source="user_roles")
    libraries = ProjectLibraryDetailSerializer(many=True, source="projectlibrary_set", read_only=True)
    invitations = InvitationSerializer(many=True)
    acl = AclField(exclude=["users"])
    settings = ProjectSettingsField(
        required=False,
        help_text=_("Project settings"),
        validators=[JSONSchemaValidator("project_settings.schema.json")],
    )

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "is_private",
            "active_after",
            "status",
            "is_active",
            "settings",
            "invitations",
            "roles",
            "libraries",
            "created_at",
            "updated_at",
            "acl",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ChangeStatusSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=ProjectStatus.choices, help_text=_("Project status"))

    class Meta:
        model = Project
        fields = ["id", "status"]
        read_only_fields = ["id"]

    def save(self, **kwargs):
        project = self.instance
        old_status = project.status
        new_status = self.validated_data.get("status")

        if old_status == new_status:
            return project

        project.status = new_status
        project.save(update_fields=["status"])

        match old_status, new_status:
            case ProjectStatus.DRAFT, ProjectStatus.REVIEW:
                # A) Send invitation emails to new users
                invite_unregistered_users_to_epl(project, self.context["request"])
                # B) Send notification to project admins (already registered) to review the project.
                # Admins that are not registered atm, will receive this notification when they create their account.
                invite_project_admins_to_review(project, self.context["request"])
            case ProjectStatus.REVIEW, ProjectStatus.READY:
                # Send notification to project managers to publish or schedule the project.
                # Project managers that are not registered atm, will receive this notification when they create their account.
                invite_project_managers_to_launch(project, self.context["request"])

        return project


class LaunchProjectSerializer(serializers.Serializer):
    active_after = serializers.DateTimeField(required=False)

    def save(self):
        project = self.context["project"]
        active_after = self.validated_data.get("active_after")

        if active_after and active_after > timezone.now():
            project.active_after = active_after
            is_starting_now = False
        else:
            project.active_after = timezone.now()
            is_starting_now = True

        project.status = ProjectStatus.LAUNCHED
        notify_project_launched(project, self.context["request"], is_starting_now)

        project.save()

        return project


class AssignRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.choices)
    user_id = serializers.UUIDField(help_text=_("User id"))
    library_id = serializers.UUIDField(help_text=_("Library id"), required=False)

    def validate_user_id(self, user_id):
        try:
            user = User.objects.active().get(pk=user_id)
        except User.DoesNotExist:
            raise serializers.ValidationError(_("User does not exist."))
        return user.id

    def validate_library_id(self, library_id):
        try:
            library = Library.objects.get(pk=library_id)
        except Library.DoesNotExist:
            raise serializers.ValidationError(_("Library does not exist."))
        return library.id

    def save(self):
        if self.context["request"].method == "POST":
            project = self.context["project"]
            request = self.context["request"]

            user_role, created = UserRole.objects.filter(
                user_id=self.validated_data["user_id"],
                role=self.validated_data["role"],
                library_id=self.validated_data.get("library_id"),
                project=project,
            ).get_or_create(
                user_id=self.validated_data["user_id"],
                role=self.validated_data["role"],
                library_id=self.validated_data.get("library_id"),
                project=project,
                assigned_by=request.user,
            )

            if created:
                # Get the user object
                user = User.objects.get(id=self.validated_data["user_id"])
                role = self.validated_data["role"]

                # Send appropriate emails based on role and project status
                if role == Role.PROJECT_ADMIN and project.status == ProjectStatus.REVIEW:
                    send_invite_project_admins_to_review_email(
                        email=user.email,
                        request=request,
                        project_name=project.name,
                        tenant_name=request.tenant.name,
                        project_creator_email=request.user.email,
                    )

                elif role == Role.PROJECT_MANAGER and project.status == ProjectStatus.READY:
                    send_invite_project_managers_to_launch_email(
                        email=user.email,
                        request=request,
                        project=project,
                        tenant_name=request.tenant.name,
                        action_user_email=request.user.email,
                    )

                elif project.status >= ProjectStatus.LAUNCHED:
                    is_starting_now = project.active_after <= timezone.now()
                    send_project_launched_email(
                        request=request,
                        project=project,
                        project_users=[user.email],
                        is_starting_now=is_starting_now,
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
            "user": NestedUserSerializer(user).data,
            "role": instance.get("role"),
            "library_id": str(instance.get("library_id")) if instance.get("library_id") else None,
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


class ExclusionReasonSerializer(serializers.Serializer):
    """
    Add or delete an exclusion reason for a project.
    """

    exclusion_reason = serializers.CharField(
        max_length=255,
        required=True,
        allow_blank=False,
        help_text=_("Exclusion reason to add or delete from the project"),
    )

    def save(self):
        project = self.context["project"]
        exclusion_reason = self.validated_data["exclusion_reason"]

        if self.context["request"].method == "POST":
            exclusion_reasons = project.settings.get("exclusion_reasons", [])

            if exclusion_reason in exclusion_reasons:
                return exclusion_reason

            project.settings["exclusion_reasons"].append(exclusion_reason)
            project.settings["exclusion_reasons"].sort()
            project.save(update_fields=["settings"])

        elif self.context["request"].method == "DELETE":
            exclusion_reasons = project.settings.get("exclusion_reasons", [])

            if exclusion_reason not in exclusion_reasons:
                return None

            project.settings["exclusion_reasons"].remove(exclusion_reason)
            project.save(update_fields=["settings"])


@extend_schema_field(load_json_schema("project_alert_settings.schema.json"))
class ProjectAlertSettingsField(serializers.JSONField):
    pass


class ProjectAlertSettingsSerializer(serializers.Serializer):
    alerts = serializers.JSONField(
        help_text="Alert settings for each alert type",
        required=True,
        validators=[JSONSchemaValidator("project_alert_settings.schema.json")],
    )

    def validate(self, attrs):
        if "alerts" not in attrs:
            raise serializers.ValidationError({"alerts": "This field is required."})
        return attrs

    def to_representation(self, instance):
        if instance and instance.settings:
            return {"alerts": instance.settings.get("alerts", {})}
        return {"alerts": {}}

    def update(self, instance: Project, validated_data: dict) -> Project:
        current_settings = instance.settings or {}
        current_settings["alerts"] = validated_data["alerts"]
        instance.settings = current_settings
        instance.save(update_fields=["settings"])
        return instance
