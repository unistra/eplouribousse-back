from unittest.mock import patch

from django.core.signing import TimestampSigner
from django_tenants.urlresolvers import reverse
from rest_framework import status

from epl.apps.user.views import INVITE_TOKEN_SALT, _get_invite_signer
from epl.tests import TestCase


class TestInviteHandshakeView(TestCase):
    def test_valid_invite_token(self):
        signer = _get_invite_signer()
        email = "new_user@example.com"
        token = signer.sign_object({"email": email})

        response = self.post(reverse("invite_handshake"), {"token": token})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], email)

    def test_expired_invite_token(self):
        signer = _get_invite_signer()
        token = signer.sign_object({"email": "new_user@example.com"})

        with patch("epl.apps.user.views.INVITE_TOKEN_MAX_AGE", 0):
            response = self.post(reverse("invite_handshake"), {"token": token})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invite token expired", str(response.content))

    def test_invalid_invite_token(self):
        response = self.post(reverse("invite_handshake"), {"token": "invalid_token"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid invite token", str(response.content))

    def test_missing_token(self):
        response = self.post(reverse("invite_handshake"), {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_malformed_token_data(self):
        signer = TimestampSigner(salt=INVITE_TOKEN_SALT)
        token = signer.sign_object({"not_email": "test@example.com"})

        response = self.post(reverse("invite_handshake"), {"token": token})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
