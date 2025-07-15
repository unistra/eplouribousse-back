from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import AuthUser
from rest_framework_simplejwt.authentication import JWTAuthentication as BaseJWTAuthentication
from rest_framework_simplejwt.tokens import Token


class JWTAuthentication(BaseJWTAuthentication):
    def authenticate(self, request: Request) -> tuple[AuthUser, Token] | None:
        result = super().authenticate(request)
        if result is None:
            return None
        user, token = result
        self._validate_audience(request, token)
        return user, token

    def _validate_audience(self, request: Request, token: Token) -> None:
        # A token is only valid for the tenant it was issued for
        if token.get("aud", "") != request.tenant.id.hex:
            raise AuthenticationFailed(_("Invalid audience"))
