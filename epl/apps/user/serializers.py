from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from epl.apps.project.models import Project
from epl.apps.user.models import User
from epl.libs.schema import load_json_schema
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


class TokenObtainSerializer(serializers.Serializer):
    refresh = serializers.CharField(read_only=True)
    access = serializers.CharField(read_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_token(self, user: User):
        token = RefreshToken.for_user(user)
        token["iss"] = self.context["request"].get_host()
        token["sub"] = str(user.pk)
        token["nbf"] = timezone.now().timestamp()
        return token

    def validate_user(self, attrs, user: User):
        if not user.is_active:
            raise ValidationError(_("User is not active"))
        data = super().validate(attrs)
        refresh = self.get_token(user)
        data["refresh"] = str(refresh)
        data["access"] = str(refresh.access_token)
        return data

    def validate(self, attrs):
        return self.validate_user(attrs, self.context["user"])


class PasswordResetSerializer(serializers.Serializer):
    token = serializers.CharField(style={"input_type": "text"}, write_only=True, required=True)
    new_password = serializers.CharField(style={"input_type": "password"}, write_only=True, required=True)
    confirm_password = serializers.CharField(style={"input_type": "password"}, write_only=True, required=True)

    def __init__(self, *args, **kwargs):
        self.email = None
        self.salt = kwargs.pop("salt", None)
        self.max_age = kwargs.pop("max_age", None)
        super().__init__(*args, **kwargs)

    def validate_token(self, attrs):
        signer = TimestampSigner(salt=self.salt)
        try:
            token_data = signer.unsign_object(attrs, max_age=self.max_age)
            self.email = token_data.get("email")

        except SignatureExpired:
            raise serializers.ValidationError(_("Signature has expired"))
        except BadSignature:
            raise serializers.ValidationError(_("Signature does not match"))
        return attrs

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(_("New password and confirm password do not match"))

        try:
            validate_password(attrs["new_password"])
        except ValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})
        return attrs

    def save(self, **kwargs):
        try:
            user = User.objects.get(email=self.email, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError(_("User not found"))
        user.set_password(self.validated_data["new_password"])
        user.save()
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
        return [role.role for role in projet.user_roles.filter(user=self.context["user"])]


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
            "settings",
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
        fields = ["id", "username", "email", "first_name", "last_name", "roles"]


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

    def validate(self, attrs):
        if User.objects.filter(email=attrs["email"]).exists():
            raise serializers.ValidationError(_("Email is already linked to an account"))
        return attrs


class InviteTokenSerializer(serializers.Serializer):
    token = serializers.CharField(write_only=True, required=True)
    email = serializers.EmailField(read_only=True)

    def __init__(self, *args, **kwargs):
        self.salt = kwargs.pop("salt", None)
        self.max_age = kwargs.pop("max_age", None)
        super().__init__(*args, **kwargs)

    def validate(self, attrs):
        invite_token = attrs.get("token")
        if not invite_token:
            raise serializers.ValidationError(_("Token is required."))

        signer = TimestampSigner(salt=self.salt)
        try:
            token_data = signer.unsign_object(invite_token, max_age=self.max_age)
            email = token_data.get("email")
            if not email:
                raise serializers.ValidationError(_("Invalid token format."))
            attrs["email"] = email
        except SignatureExpired:
            raise serializers.ValidationError(_("Invite token expired"))
        except BadSignature:
            raise serializers.ValidationError(_("Invalid invite token"))

        return attrs


class CreateAccountSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    password = serializers.CharField(style={"input_type": "password"}, write_only=True, required=True)
    confirm_password = serializers.CharField(style={"input_type": "password"}, write_only=True, required=True)

    def __init__(self, *args, **kwargs):
        self.email = None
        self.salt = kwargs.pop("salt", None)
        self.max_age = kwargs.pop("max_age", None)
        super().__init__(*args, **kwargs)

    def validate_token(self, token_value):
        token_serializer = InviteTokenSerializer(data={"token": token_value}, salt=self.salt, max_age=self.max_age)
        token_serializer.is_valid(raise_exception=True)

        self.email = token_serializer.validated_data.get("email")
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
        user = User.objects.create_user(email=self.email, password=self.validated_data["password"])
        return user
