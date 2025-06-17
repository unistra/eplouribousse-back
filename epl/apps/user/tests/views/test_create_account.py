from unittest.mock import patch

from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context
from rest_framework import status

from epl.apps.user.models import User
from epl.apps.user.views import _get_invite_signer
from epl.tests import TestCase


class TestCreateAccountView(TestCase):
    def test_successful_account_creation(self):
        signer = _get_invite_signer()
        email = "new_user@example.com"
        token = signer.sign_object({"email": email})

        response = self.post(
            reverse("create_account"),
            {"token": token, "password": "SecurePassword123!", "confirm_password": "SecurePassword123!"},
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        with tenant_context(self.tenant):
            self.assertTrue(User.objects.filter(email=email).exists())

    def test_password_mismatch(self):
        signer = _get_invite_signer()
        email = "new_user@example.com"
        token = signer.sign_object({"email": email})

        response = self.post(
            reverse("create_account"),
            {"token": token, "password": "SecurePassword123!", "confirm_password": "DifferentPassword123!"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Password and confirm password do not match", str(response.content))

    def test_invalid_token(self):
        response = self.post(
            reverse("create_account"),
            {"token": "invalid_token", "password": "SecurePassword123!", "confirm_password": "SecurePassword123!"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue("invalid invite token" in str(response.content).lower())

    def test_expired_token(self):
        signer = _get_invite_signer()
        email = "new_user@example.com"
        token = signer.sign_object({"email": email})

        with patch("epl.apps.user.views.INVITE_TOKEN_MAX_AGE", 0):
            response = self.post(
                reverse("create_account"),
                {"token": token, "password": "SecurePassword123!", "confirm_password": "SecurePassword123!"},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invite token expired", str(response.content))
