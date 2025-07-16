from django.utils.translation import gettext_lazy as _
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CustomJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "epl.apps.user.authentication.JWTAuthentication"
    name = "JWT"
    match_subclasses = False

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            # "in": "header",
            # "name": "Authorization",
            "description": _("Use the JWT token in the format: Bearer <token>"),
        }
