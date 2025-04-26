from rest_framework import serializers


class UnauthorizedSerializer(serializers.Serializer):
    detail = serializers.CharField(help_text="Error message explaining the reason for the error")


class ValidationErrorSerializer(serializers.Serializer):
    field_name = serializers.ListField(
        child=serializers.CharField(),
    )
    non_field_errors = serializers.ListField(
        child=serializers.CharField(),
    )
