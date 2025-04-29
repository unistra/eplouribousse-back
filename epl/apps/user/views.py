from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from epl.apps.user.models import User
from epl.apps.user.serializers import PasswordChangeSerializer, PasswordResetSerializer
from epl.schema_serializers import UnauthorizedSerializer, ValidationErrorSerializer
from epl.services.user.email import send_password_change_email, send_password_reset_email


@extend_schema(
    tags=["User"],
    summary=_("Change the user's password"),
    request=PasswordChangeSerializer,
    responses={
        status.HTTP_200_OK: inline_serializer(
            name="PasswordChangedSerializer",
            fields={"detail": serializers.CharField(help_text=_("Confirmation message"))},
        ),
        status.HTTP_400_BAD_REQUEST: ValidationErrorSerializer,
        status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
    },
)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def change_password(request: Request) -> Response:
    """
    Change the user's password and send an email confirming the change
    """
    serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()

    send_password_change_email(request.user)
    return Response({"detail": _("Your password has been changed successfully.")}, status=status.HTTP_200_OK)


@extend_schema(
    tags=["User"],
    summary=_("Reset the user's password"),
    request=PasswordResetSerializer,
    responses={
        status.HTTP_200_OK: inline_serializer(
            name="PasswordResettedSerializer",
            fields={"detail": serializers.CharField(help_text=_("Confirmation message"))},
        ),
        status.HTTP_400_BAD_REQUEST: ValidationErrorSerializer,
    },
)
@api_view(["PATCH"])
def reset_password(request: Request) -> Response:
    serializer = PasswordResetSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()

    return Response({"detail": _("Your password has been resetted successfully.")}, status=status.HTTP_200_OK)


@api_view(["POST"])
def send_reset_email(request: Request) -> Response:
    email = request.data["email"]
    try:
        protocol = request.scheme
        domain = request.tenant.domains.get(is_primary=True)
        user = User.objects.get(email=email)
        if protocol == "http":
            port = ":5173"
        send_password_reset_email(user, email, domain.front_domain, protocol, port)
    finally:
        return Response({"detail": _("Email has been sent successfully.")}, status=status.HTTP_200_OK)
