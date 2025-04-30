import logging

from django.core import signing
from django.http import HttpResponseRedirect
from django.utils.encoding import iri_to_uri
from django.utils.translation import gettext_lazy as _
from django.views.defaults import permission_denied
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from epl.apps.user.models import User
from epl.apps.user.serializers import (
    PasswordChangeSerializer,
    PasswordResetSerializer,
    TokenObtainSerializer,
    UserSerializer,
)
from epl.schema_serializers import UnauthorizedSerializer, ValidationErrorSerializer
from epl.services.user.email import send_password_change_email, send_password_reset_email

logger = logging.getLogger(__name__)

HANDSHAKE_TOKEN_MAX_AGE = 60
HANDSHAKE_TOKEN_SALT = f"{__file__}:handshake"


@extend_schema(
    tags=["user"],
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
    tags=["user"],
    summary="Reset the user's password",
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
    """
    Reset the user's password
    """
    serializer = PasswordResetSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()

    return Response({"detail": _("Your password has been successfully reset.")}, status=status.HTTP_200_OK)


@extend_schema(
    tags=["user"],
    summary="Send a token to the user to reset the password",
    request=inline_serializer(
        name="SendResetEmailSerializer",
        fields={"email": serializers.EmailField(help_text="Email address", write_only=True)},
    ),
    responses={
        status.HTTP_200_OK: inline_serializer(
            name="SendResetEmailResponseSerializer",
            fields={"detail": serializers.CharField(help_text=_("Confirmation message"), read_only=True)},
        ),
    },
)
@api_view(["POST"])
def send_reset_email(request: Request) -> Response:
    """
    Email the user with a token to reset the password
    If the user's email is not found nothing happens
    """
    email = request.data["email"]
    try:
        protocol = request.scheme
        domain = request.tenant.domains.get(is_primary=True)
        user = User.objects.get(email=email, is_active=True)
        if protocol == "http":
            port = ":5173"
        send_password_reset_email(user, email, domain.front_domain, protocol, port)
    finally:
        return Response({"detail": _("Email has been sent successfully.")}, status=status.HTTP_200_OK)


def login_success(request) -> HttpResponseRedirect:
    """
    We successfully logged in. Redirect to the front with an authentication token
    The front can use that token to get a JWT token
    """
    if not request.user.is_authenticated:
        return permission_denied(request, _("You must be logged in to access this page"))
    signer = _get_handshake_signer()
    authentication_token: str = signer.sign_object({"u": str(request.user.id)})
    front_url = f"{request.scheme}://{request.tenant.domains.get(is_primary=True).front_domain}/handshake?t={authentication_token}"
    logger.info(f"Successful login: redirect to front at {front_url}")

    return HttpResponseRedirect(iri_to_uri(front_url))


@extend_schema(
    tags=["user"],
    summary=_("Validate a handshake token"),
    request=inline_serializer(
        name="HandshakeSerializer",
        fields={"t": serializers.CharField(help_text=_("Handshake token"))},
    ),
    responses={
        status.HTTP_200_OK: TokenObtainSerializer,
        status.HTTP_400_BAD_REQUEST: ValidationErrorSerializer,
        status.HTTP_403_FORBIDDEN: None,
    },
)
@api_view(["POST"])
def login_handshake(request: Request) -> Response:
    """
    We received a handshake token from the front, let's:
     - validate the token
     - load the corresponding user
     - return a JWT for that user
    To be valid, the token must not be older than HANDSHAKE_TOKEN_MAX_AGE (60) seconds
    """
    signer: signing.TimestampSigner = _get_handshake_signer()
    handshake_token: str = request.data.get("t", "")

    try:
        user_data = signer.unsign_object(handshake_token, max_age=HANDSHAKE_TOKEN_MAX_AGE)
        user_id = user_data.get("u", None)
        user = User.objects.get(pk=user_id, is_active=True)
    except signing.SignatureExpired:
        raise PermissionDenied(_("Handshake token expired"))
    except (signing.BadSignature, User.DoesNotExist):
        raise PermissionDenied(_("Invalid handshake token"))

    serializer = TokenObtainSerializer(data={}, context={"user": user, "request": request})
    if serializer.is_valid(raise_exception=True):
        logger.info(f"Successful handshake for user {user.id}")
        return Response(serializer.validated_data)

    return Response({"token": handshake_token})


def _get_handshake_signer() -> signing.TimestampSigner:
    return signing.TimestampSigner(salt=HANDSHAKE_TOKEN_SALT)


@extend_schema(
    tags=["user"],
    summary=_("User profile"),
    responses={
        status.HTTP_200_OK: UserSerializer,
        status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_info(request):
    """
    Display user information.
    """
    current_user = request.user
    serializer = UserSerializer(current_user)
    return Response(serializer.data, status=status.HTTP_200_OK)
