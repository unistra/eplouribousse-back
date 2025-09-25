from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import IntegrityError, transaction
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from rest_framework_simplejwt.serializers import AuthUser
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer as BaseTokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken, Token

from epl.apps.project.models import Project, ProjectStatus, Role
from epl.apps.user.models import User
from epl.libs.schema import load_json_schema
from epl.services.user.email import (
    send_account_created_email,
    send_invite_project_admins_to_review_email,
    send_invite_project_managers_to_launch_email,
    send_password_change_email,
)
from epl.validators import JSONSchemaValidator


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(style={"input_type": "password"}, write_only=True, required=True)
    new_password = serializers.CharField(style={"input_type": "password"}, write_only=True, required=True)
    confirm_password = serializers.CharField(style={"input_type": "password"}, write_only=True, required=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError(_("Old password is incorrect"))
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(_("New password and confirm password do not match"))

        try:
            validate_password(attrs["new_password"])
        except ValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user


class TokenObtainPairSerializer(BaseTokenObtainPairSerializer):
    # We add the audience to the token to ensure it is valid for the current tenant only
    def get_token(self, user: AuthUser) -> Token:
        token = super().get_token(user)
        token["aud"] = self.context["request"].tenant.id.hex
        return token


class TokenObtainSerializer(serializers.Serializer):
    # We need this for external authentication as the
    # BaseTokenObtainPairSerializer expects username and password fields
    refresh = serializers.CharField(read_only=True)
    access = serializers.CharField(read_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_token(self, user: User):
        token = RefreshToken.for_user(user)
        token["aud"] = self.context["request"].tenant.id.hex
        return token

    def validate_user(self, attrs, user: User):
        if not user.is_active:
            raise ValidationError(_("User is inactive"))
        data = super().validate(attrs)
        refresh = self.get_token(user)
        data["refresh"] = str(refresh)
        data["access"] = str(refresh.access_token)
        return data

    def validate(self, attrs):
        return self.validate_user(attrs, self.context["user"])


class PasswordResetSerializer(serializers.Serializer):
    uidb64 = serializers.CharField(style={"input_type": "text"}, write_only=True, required=True)
    token = serializers.CharField(style={"input_type": "text"}, write_only=True, required=True)
    new_password = serializers.CharField(style={"input_type": "password"}, write_only=True, required=True)
    confirm_password = serializers.CharField(style={"input_type": "password"}, write_only=True, required=True)

    def validate_uidb64(self, uidb64: str) -> User:
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError(_("Invalid uidb64"))
        return user

    def validate_new_password(self, new_password: str):
        try:
            validate_password(new_password)
        except ValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})
        return new_password

    def validate(self, validated_data):
        if validated_data["new_password"] != validated_data["confirm_password"]:
            raise serializers.ValidationError(_("New password and confirm password do not match"))
        if PasswordResetTokenGenerator().check_token(validated_data["uidb64"], validated_data["token"]) is False:
            raise serializers.ValidationError(_("Token is invalid or has already been used"))
        return validated_data

    def save(self, **kwargs):
        user = self.validated_data["uidb64"]
        user.set_password(self.validated_data["new_password"])
        user.save()
        send_password_change_email(user)
        return user


@extend_schema_field(load_json_schema("user_settings.schema.json"))
class UserSettingsField(serializers.JSONField): ...


class UserNestedProjectSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField(help_text=_("User's roles in the project"))

    class Meta:
        model = Project
        fields = [
            "id",
            "roles",
            "name",
        ]

    def get_roles(self, projet: Project) -> list[str]:
        """
        Get all roles of the user in the project.
        """
        return [str(role.role) for role in projet.user_roles.filter(user=self.context["user"])]


class UserSerializer(ModelSerializer):
    """
    This Serializer is used to perform GET operations on user objects.
    """

    projects = serializers.SerializerMethodField()
    can_authenticate_locally = serializers.SerializerMethodField(
        help_text=_("Whether the user can log in locally with username and password?"),
        read_only=True,
    )
    settings = UserSettingsField(
        required=False,
        help_text=_("User settings"),
        validators=[JSONSchemaValidator("user_settings.schema.json")],
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "can_authenticate_locally",
            "is_project_creator",
            "is_superuser",
            "settings",
            "projects",
        ]
        read_only_fields = [
            "id",
            "username",
            "email",
            "can_authenticate_locally",
            "is_project_creator",
            "is_superuser",
            "projects",
        ]

    def get_projects(self, user: User):
        """
        Get all projects where the user has a role.
        """
        projects = Project.objects.filter(user_roles__user=user).distinct()
        serializer = UserNestedProjectSerializer(projects, many=True, context={"user": user})
        return serializer.data

    def get_can_authenticate_locally(self, user: User) -> bool:
        return user.has_usable_password()


class ProjectUserSerializer(serializers.ModelSerializer):
    roles = serializers.ListField(
        child=serializers.CharField(help_text=_("Role in project")), help_text=_("User's roles in this project")
    )

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "roles", "is_superuser"]


class NestedUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "email"]


class UserListSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
        ]


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    project_id = serializers.CharField(required=False, allow_blank=True)
    library_id = serializers.CharField(required=False, allow_blank=True)
    role = serializers.ChoiceField(required=False, choices=Role.choices)

    def validate_project_id(self, value):
        if value and not Project.objects.filter(id=value).exists():
            raise serializers.ValidationError(_("Project does not exist."))
        return value

    def validate_library_id(self, value):
        if value and not Project.objects.filter(libraries__id=value).exists():
            raise serializers.ValidationError(_("Library does not exist."))
        return value

    def validate_role(self, value):
        if value and value not in [choice[0] for choice in Role.choices]:
            raise serializers.ValidationError(_("Invalid role."))
        return value

    def validate(self, attrs):
        if User.objects.filter(email=attrs["email"]).exists():
            raise serializers.ValidationError(_("Email is already linked to an account"))
        return attrs


class InviteTokenSerializer(serializers.Serializer):
    token = serializers.CharField(write_only=True, required=True)
    email = serializers.EmailField(read_only=True)
    project_id = serializers.CharField(read_only=True, required=False)
    library_id = serializers.CharField(read_only=True, required=False)
    role = serializers.CharField(read_only=True, required=False)
    assigned_by_id = serializers.CharField(read_only=True, required=False)

    def validate(self, attrs):
        invite_token = attrs.get("token")

        if not invite_token:
            raise serializers.ValidationError(_("Token is required."))

        signer = TimestampSigner(salt=self.context["salt"])
        try:
            token_data = signer.unsign_object(invite_token, max_age=self.context["max_age"])
            email = token_data.get("email")
            if not email:
                raise serializers.ValidationError(_("Invalid token format."))
            attrs["email"] = email
            attrs["project_id"] = token_data.get("project_id")
            attrs["library_id"] = token_data.get("library_id")
            attrs["role"] = token_data.get("role")
            attrs["assigned_by_id"] = token_data.get("assigned_by_id")

        except SignatureExpired:
            raise serializers.ValidationError(_("Invite token expired"))
        except BadSignature:
            raise serializers.ValidationError(_("Invalid invite token"))

        return attrs


class CreateAccountFromTokenSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    password = serializers.CharField(style={"input_type": "password"}, write_only=True, required=True)
    confirm_password = serializers.CharField(style={"input_type": "password"}, write_only=True, required=True)

    def __init__(self, *args, **kwargs):
        self.email = None
        self.project_id = None
        self.library_id = None
        self.role = None
        self.assigned_by_id = None
        super().__init__(*args, **kwargs)

    def validate_token(self, token_value):
        token_serializer = InviteTokenSerializer(
            data={"token": token_value},
            context=self.context,
        )
        token_serializer.is_valid(raise_exception=True)

        self.email = token_serializer.validated_data.get("email")
        self.project_id = token_serializer.validated_data.get("project_id")
        self.library_id = token_serializer.validated_data.get("library_id")
        self.role = token_serializer.validated_data.get("role")
        self.assigned_by_id = token_serializer.validated_data.get("assigned_by_id")
        return token_value

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(_("Password and confirm password do not match"))

        try:
            validate_password(attrs["password"])
        except ValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})

        return attrs

    def save(self, **kwargs):
        try:
            with transaction.atomic():
                user = User.objects.create_user(email=self.email, password=self.validated_data["password"])

                # send account creation confirmation email to a user
                request = self.context["request"]
                send_account_created_email(user, request)

                # If there is a project_id and a role, we assign the user to the project with the specified role.
                if self.project_id and self.role:
                    try:
                        project = Project.objects.get(id=self.project_id)
                    except Project.DoesNotExist:
                        raise serializers.ValidationError(
                            _("The project associated with this invitation no longer exists.")
                        )

                    # We check if user that assigned the role still exists, for better clarity in the error message.
                    assigned_by = None
                    if self.assigned_by_id:
                        try:
                            assigned_by = User.objects.get(id=self.assigned_by_id)
                        except User.DoesNotExist:
                            raise serializers.ValidationError(
                                _("Invitation expired. The user who sent the invitation no longer exists.")
                            )
                    user_role_data = {
                        "user": user,
                        "role": self.role,
                        "assigned_by": assigned_by,
                    }

                    # Check if the email is in the project's invitations
                    invited_emails = [invitation.get("email") for invitation in (project.invitations or [])]
                    if self.email not in invited_emails:
                        raise serializers.ValidationError(_("This email is not invited to join this project."))

                    if self.library_id:
                        try:
                            library = project.libraries.get(pk=self.library_id)
                            user_role_data["library"] = library
                        except ObjectDoesNotExist:
                            raise serializers.ValidationError(
                                _("The library associated with this invitation no longer exists.")
                            )

                    project.user_roles.create(**user_role_data)
                    request = self.context["request"]

                    # Post-creation actions:
                    # If the user has a project_admin role, he is notified that he must review the project's settings.
                    if self.role == Role.PROJECT_ADMIN and project.status == ProjectStatus.REVIEW:
                        send_invite_project_admins_to_review_email(
                            email=user.email,
                            request=request,
                            project_name=project.name,
                            tenant_name=request.tenant.name,
                            project_creator_email=assigned_by.email if assigned_by else None,
                        )
                    # If the user has a project_manager role, and the project status is READY, he is notified that he must launch or schedule the project start
                    if self.role == Role.PROJECT_MANAGER and project.status == ProjectStatus.READY:
                        send_invite_project_managers_to_launch_email(
                            email=user.email,
                            request=request,
                            project=project,
                            tenant_name=request.tenant.name,
                            action_user_email=assigned_by.email if assigned_by else None,
                        )

                    # If the user has an invitation pending in project.invitations, it is removed.
                    if self.email in [invitation.get("email") for invitation in project.invitations]:
                        project.invitations = [
                            invitation for invitation in project.invitations if invitation.get("email") != self.email
                        ]
                        project.save()
            return user
        except (IntegrityError, ObjectDoesNotExist) as e:
            raise serializers.ValidationError(str(e))


class UserAlertSettingsSerializer(serializers.Serializer):
    project_id = serializers.UUIDField()
    alert_type = serializers.CharField()
    enabled = serializers.BooleanField()

    def update(self, instance, validated_data):
        alerts = instance.settings.setdefault("alerts", {})
        project_alerts = alerts.setdefault(str(validated_data["project_id"]), {})
        project_alerts[validated_data["alert_type"]] = validated_data["enabled"]
        instance.settings["alerts"] = alerts
        instance.save(update_fields=["settings"])
        return instance
