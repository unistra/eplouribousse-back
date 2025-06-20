import json

from django.utils.translation import gettext as _
from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context
from rest_framework import status

from epl.apps.user.models import User
from epl.tests import TestCase


class TestInviteView(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.user = User.objects.create_user(email="test_user@example.com", password="secure_password123")  # noqa: S106

    def test_invite_authenticated_access(self):
        response = self.post(reverse("invite"), {"email": "new_user@example.com"}, user=self.user)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invite_unauthenticated_access_forbidden(self):
        response = self.client.post(
            reverse("invite"), {"email": "new_user@example.com"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invite_with_existing_email(self):
        with tenant_context(self.tenant):
            User.objects.create_user(email="existing@example.com")

        response = self.post(reverse("invite"), {"email": "existing@example.com"}, user=self.user)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = json.loads(response.content.decode())
        self.assertIn(str(_("Email is already linked to an account")), data["nonFieldErrors"][0])

    def test_invite_with_invalid_email(self):
        response = self.post(reverse("invite"), {"email": "not-an-email"}, user=self.user)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
