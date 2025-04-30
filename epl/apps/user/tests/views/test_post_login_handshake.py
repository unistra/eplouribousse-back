import uuid
from unittest.mock import patch

from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context
from rest_framework import status

from epl.apps.user.models import User
from epl.apps.user.views import _get_handshake_signer
from epl.tests import TestCase


class LoginSuccessViewTest(TestCase):
    def test_anonymous_access_is_denied(self):
        response = self.client.get(reverse("login_success"))
        self.response_forbidden(response)

    def test_logged_in_user_is_redirected_to_front_with_token(self):
        domain = self.tenant.domains.get(is_primary=True)
        domain.front_domain = "front"
        domain.save()
        with tenant_context(self.tenant):
            user = User.objects.create_user(email="first.last@example.com")
        self.client.force_login(user)
        response = self.client.get(reverse("login_success"))
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn("http://front/handshake?t=", response.url)


class HandshakeViewTest(TestCase):
    def test_missing_token_is_denied(self):
        response = self.client.post(reverse("login_handshake"))
        self.response_forbidden(response)

    def test_invalid_token_is_denied(self):
        response = self.client.post(reverse("login_handshake"), {"t": "invalid_token"})
        self.response_forbidden(response)

    def test_expired_token_is_denied(self):
        signer = _get_handshake_signer()
        token = signer.sign_object({"u": str(uuid.uuid4())})
        with patch("epl.apps.user.views.HANDSHAKE_TOKEN_MAX_AGE", 0):
            response = self.client.post(reverse("login_handshake"), {"t": token})
        self.response_forbidden(response)
        self.assertIn("Handshake token expired", str(response.content))

    def test_active_user_returns_jwt(self):
        with tenant_context(self.tenant):
            user = User.objects.create_user(email="first.last@example.com", is_active=True)
        signer = _get_handshake_signer()
        token = signer.sign_object({"u": str(user.id)})
        response = self.client.post(reverse("login_handshake"), {"t": token})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_inactive_user_is_denied(self):
        with tenant_context(self.tenant):
            user = User.objects.create_user(email="first.last@example.com", is_active=False)
        signer = _get_handshake_signer()
        token = signer.sign_object({"u": str(user.id)})
        response = self.client.post(reverse("login_handshake"), {"t": token})
        self.response_forbidden(response)
