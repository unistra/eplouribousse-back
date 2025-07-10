import uuid

from django_tenants.test.client import TenantRequestFactory
from django_tenants.utils import tenant_context
from rest_framework.exceptions import AuthenticationFailed

from epl.apps.project.tests.factories.user import UserFactory
from epl.apps.user.authentication import JWTAuthentication
from epl.apps.user.serializers import TokenObtainPairSerializer
from epl.tests import TestCase


class JWTAuthenticationTestCase(TestCase):
    def test_jwt_contains_aud_claim(self):
        refresh_token = self._get_token()

        self.assertIn("aud", refresh_token)
        self.assertEqual(refresh_token["aud"], str(self.tenant.id.hex))

    def _get_token(self):
        request = TenantRequestFactory(self.tenant).get("/")
        with tenant_context(self.tenant):
            user = UserFactory()
        refresh_token = TokenObtainPairSerializer(data={}, context={"request": request}).get_token(user)
        return refresh_token

    def test_validate_token_with_valid_audience(self):
        refresh_token = self._get_token()
        request = TenantRequestFactory(self.tenant).get("/")
        request.tenant = self.tenant

        exception_raised = False
        try:
            JWTAuthentication()._validate_audience(request, refresh_token.access_token)
        except AuthenticationFailed:
            exception_raised = True

        self.assertFalse(exception_raised)

    def test_validate_token_with_invalid_audience(self):
        refresh_token = self._get_token()
        refresh_token["aud"] = str(uuid.uuid4())

        # Create a request with another tenant
        request = TenantRequestFactory(self.tenant).get("/")
        request.tenant = self.tenant

        with self.assertRaises(AuthenticationFailed):
            JWTAuthentication()._validate_audience(request, refresh_token.access_token)
