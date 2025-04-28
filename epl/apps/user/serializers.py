from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


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


class PasswordResetSerializer(serializers.Serializer):
    token = serializers.CharField(style={"input_type": "text"}, write_only=True, required=True)
    new_password = serializers.CharField(style={"input_type": "password"}, write_only=True, required=True)
    confirm_password = serializers.CharField(style={"input_type": "password"}, write_only=True, required=True)

    def validate_token(self, attrs):
        _user = self.context["request"].user
        signer = TimestampSigner(salt="reset-password")
        try:
            _email = signer.unsign(attrs["token"], max_age=60 * 60 * 24)
        except BadSignature:
            raise serializers.ValidationError("Signature does not match")
        except SignatureExpired:
            raise serializers.ValidationError("Signature has expired")
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
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user
