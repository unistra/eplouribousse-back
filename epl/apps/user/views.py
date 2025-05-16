import logging

from django.core import signing
from django.http import HttpResponseRedirect
from django.utils.encoding import iri_to_uri
from django.utils.translation import gettext_lazy as _
from django.views.defaults import permission_denied
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view, inline_serializer
from rest_framework import filters, mixins, serializers, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from epl.apps.user.models import User
from epl.apps.user.serializers import (
    CreateAccountSerializer,
    EmailSerializer,
    InviteTokenSerializer,
    PasswordChangeSerializer,
    PasswordResetSerializer,
    TokenObtainSerializer,
    UserListSerializer,
    UserSerializer,
)
from epl.libs.pagination import PageNumberPagination
from epl.schema_serializers import UnauthorizedSerializer, ValidationErrorSerializer
from epl.services.user.email import send_invite_email, send_password_change_email, send_password_reset_email

logger = logging.getLogger(__name__)

HANDSHAKE_TOKEN_MAX_AGE = 60
HANDSHAKE_TOKEN_SALT = f"{__file__}:handshake"

RESET_TOKEN_MAX_AGE = 3600  # 1 hour
RESET_TOKEN_SALT = f"{__file__}:reset"

INVITE_TOKEN_MAX_AGE = 60 * 60 * 24 * 7  # 7 days
INVITE_TOKEN_SALT = f"{__file__}:invite"


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


def _get_reset_password_signer() -> signing.TimestampSigner:
    return signing.TimestampSigner(salt=RESET_TOKEN_SALT)


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
    serializer = PasswordResetSerializer(
        data=request.data, context={"request": request}, salt=RESET_TOKEN_SALT, max_age=RESET_TOKEN_MAX_AGE
    )
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
    If the user's email is not found, nothing happens
    """
    email = request.data.get("email")
    if not email:
        return Response({"detail": _("Email is required.")}, status=status.HTTP_400_BAD_REQUEST)

    protocol = request.scheme
    port = ":5173" if protocol == "http" else ""

    signer = _get_reset_password_signer()
    token = signer.sign_object({"email": email})
    front_url = f"{protocol}://{request.tenant.get_primary_domain().front_domain}{port}/reset-password?token={token}"

    try:
        user = User.objects.get(email=email, is_active=True)
        send_password_reset_email(user, front_url)
    except User.DoesNotExist:
        # Intentionally do nothing if the user does not exist
        pass

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
    front_url = (
        f"{request.scheme}://{request.tenant.get_primary_domain().front_domain}/handshake?t={authentication_token}"
    )
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
def user_profile(request):
    """
    Retrieve user profile
    """
    current_user = request.user
    serializer = UserSerializer(current_user, context={"request": request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(
        tags=["user"],
        summary=_("List of users"),
        parameters=[
            OpenApiParameter(
                "search",
                OpenApiTypes.STR,
                OpenApiParameter.QUERY,
                description=_("Search string"),
                required=False,
            )
        ],
        responses={
            status.HTTP_200_OK: UserListSerializer(many=True),
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
        },
    )
)
class UserViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    List and search active users
    """

    queryset = User.objects.active()
    serializer_class = UserListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["first_name", "last_name", "email", "username"]
    ordering_fields = ["first_name", "last_name", "email"]


def _get_invite_signer() -> signing.TimestampSigner:
    return signing.TimestampSigner(salt=INVITE_TOKEN_SALT)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def invite(request: Request) -> Response:
    serializer = EmailSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        send_invite_email(email=request.data["email"], request=request, signer=_get_invite_signer())
        return Response(status=status.HTTP_200_OK)
    except Exception:
        return Response({"details": _("Email sending failed")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
def invite_handshake(request: Request) -> Response:
    serializer = InviteTokenSerializer(data=request.data, salt=INVITE_TOKEN_SALT, max_age=INVITE_TOKEN_MAX_AGE)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data.get("email")
    return Response({"email": email}, status=status.HTTP_200_OK)


@api_view(["POST"])
def create_account(request: Request) -> Response:
    serializer = CreateAccountSerializer(
        data=request.data, context={"request": request}, salt=INVITE_TOKEN_SALT, max_age=INVITE_TOKEN_MAX_AGE
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    return Response({"detail": _("Account created successfully.")}, status=status.HTTP_201_CREATED)
