import logging

from django.core import signing
from django.http import HttpResponseRedirect
from django.utils.encoding import iri_to_uri
from django.utils.translation import gettext_lazy as _
from django.views.defaults import permission_denied
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view, inline_serializer
from ipware import get_client_ip
from rest_framework import filters, mixins, serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from epl.apps.project.models import ActionLog
from epl.apps.user.models import User
from epl.apps.user.serializers import (
    CreateAccountFromTokenSerializer,
    EmailSerializer,
    InviteTokenSerializer,
    PasswordChangeSerializer,
    PasswordResetSerializer,
    TokenObtainSerializer,
    UserListSerializer,
    UserSerializer,
)
from epl.libs.filters import ExcludeFilter
from epl.libs.pagination import PageNumberPagination
from epl.permissions import IsSuperUser
from epl.schema_serializers import UnauthorizedSerializer, ValidationErrorSerializer
from epl.services.tenant import get_front_domain
from epl.services.user.email import send_invite_to_epl_email, send_password_change_email, send_password_reset_email

logger = logging.getLogger(__name__)

HANDSHAKE_TOKEN_MAX_AGE = 60
HANDSHAKE_TOKEN_SALT = f"{__name__}:handshake"

RESET_TOKEN_MAX_AGE = 3600  # 1 hour
RESET_TOKEN_SALT = f"{__name__}:reset"

INVITE_TOKEN_MAX_AGE = 60 * 60 * 24 * 7  # 7 days
INVITE_TOKEN_SALT = f"{__name__}:invite"


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
    ActionLog.log(
        message="User has changed their password",
        actor=request.user,
        obj=request.user,
        ip=get_client_ip(request)[0],
    )
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
    serializer = PasswordResetSerializer(
        data=request.data,
        context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    ActionLog.log(message="User has reset their password", actor=user, obj=user, ip=get_client_ip(request)[0])

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
def send_reset_email(request):
    """
    Email the user with a token to reset the password
    If the user's email is not found, nothing happens
    """
    email = request.data.get("email", "")
    front_domain = get_front_domain(request)

    try:
        user = User.objects.active().get(email=email)
        send_password_reset_email(user, front_domain)
        ActionLog.log(message="User has requested a password reset", actor=user, obj=user, ip=get_client_ip(request)[0])
    except User.DoesNotExist:
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
    ActionLog.log(message="User has logged in", actor=request.user, obj=request.user, ip=get_client_ip(request)[0])

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
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, ExcludeFilter]
    search_fields = ["first_name", "last_name", "email", "username"]
    ordering_fields = ["first_name", "last_name", "email"]

    @extend_schema(
        tags=["user"],
        summary=_("Get, set or delete a user's project creator role"),
        description=_("Check if a user has project creator role or set or delete that role"),
        request=None,
        responses={
            status.HTTP_200_OK: inline_serializer(
                name="ProjectCreatorResponse",
                fields={"is_project_creator": serializers.BooleanField(help_text=_("User is project creator"))},
            ),
            status.HTTP_401_UNAUTHORIZED: UnauthorizedSerializer,
            status.HTTP_405_METHOD_NOT_ALLOWED: None,
        },
    )
    @action(
        methods=["GET", "POST", "DELETE"],
        detail=True,
        permission_classes=[IsSuperUser],
        url_path="project-creator",
    )
    def project_creator(self, request, pk=None):
        user = self.get_object()
        if not request.user.is_superuser:
            raise PermissionDenied(_("Only superusers can set a user as project creator"))

        match request.method:
            case "GET":
                return Response({"is_project_creator": user.is_project_creator})
            case "POST":
                user.set_is_project_creator(True, request.user)
                return Response({"is_project_creator": user.is_project_creator})
            case "DELETE":
                user.set_is_project_creator(False, request.user)
                return Response({"is_project_creator": user.is_project_creator})
            case _:
                return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


def _get_invite_signer() -> signing.TimestampSigner:
    return signing.TimestampSigner(salt=INVITE_TOKEN_SALT)


@extend_schema(
    tags=["user"],
    summary=_("Send an invitation email"),
    request=EmailSerializer,
    responses={
        status.HTTP_200_OK: inline_serializer(
            name="InviteSuccessResponse",
            fields={"detail": serializers.CharField(help_text=_("Invitation email sent successfully."))},
        )
    },
)
@api_view(["POST"])
@permission_classes([IsSuperUser])
def invite(request: Request) -> Response:
    serializer = EmailSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    send_invite_to_epl_email(
        email=serializer.validated_data.get("email"),
        project_id=serializer.validated_data.get("project_id"),
        library_id=serializer.validated_data.get("library_id"),
        role=serializer.validated_data.get("role"),
        assigned_by_id=request.user.id,
        request=request,
        signer=_get_invite_signer(),
    )
    return Response(status=status.HTTP_200_OK)


def _get_context_for_invite_and_create_account(request: Request) -> dict:
    return {"request": request, "salt": INVITE_TOKEN_SALT, "max_age": INVITE_TOKEN_MAX_AGE}


@extend_schema(
    tags=["user"],
    summary=_("Validate invitation token"),
    description=_("Validates an invitation token and returns the associated email address if valid."),
    request=InviteTokenSerializer,
    responses={
        status.HTTP_200_OK: inline_serializer(
            name="InviteTokenResponseSerializer",
            fields={"email": serializers.EmailField(help_text=_("Email address associated with the invitation"))},
        ),
        status.HTTP_400_BAD_REQUEST: ValidationErrorSerializer,
    },
)
@api_view(["POST"])
def invite_handshake(request: Request) -> Response:
    serializer = InviteTokenSerializer(
        data=request.data,
        context=_get_context_for_invite_and_create_account(request),
    )
    serializer.is_valid(raise_exception=True)

    return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["user"],
    summary=_("Create a new user account"),
    description=_("Creates a new user account based on an invitation token"),
    request=CreateAccountFromTokenSerializer,
    responses={
        status.HTTP_201_CREATED: inline_serializer(
            name="AccountCreatedResponse",
            fields={"detail": serializers.CharField(help_text=_("Account created successfully."))},
        ),
        status.HTTP_400_BAD_REQUEST: ValidationErrorSerializer,
    },
)
@api_view(["POST"])
def create_account(request: Request) -> Response:
    serializer = CreateAccountFromTokenSerializer(
        data=request.data, context=_get_context_for_invite_and_create_account(request)
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    return Response({"detail": _("Account created successfully.")}, status=status.HTTP_201_CREATED)
