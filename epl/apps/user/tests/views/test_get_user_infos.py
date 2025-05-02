from django.urls import reverse
from django_tenants.utils import tenant_context

from epl.apps.user.models import User
from epl.tests import TestCase


class TestUserInfosView(TestCase):
    def setUp(self):
        """
        Set up the test case.
        """
        super().setUp()  # Initialize client and tenant
        with tenant_context(self.tenant):  # Create the user within the tenant context
            self.user = User.objects.create_user(
                email="test_email@example.com",
            )

    def test_get_user_infos_success(self):
        """
        Test the successful retrieval of user information.
        """
        url = reverse("user")
        response = self.get(url, user=self.user)

        self.response_ok(response)
        self.assertEqual(response.data["username"], self.user.username)

    def test_get_user_infos_unauthenticated(self):
        """
        Test that unauthenticated users cannot access user information.
        """
        url = reverse("user")
        response = self.client.get(url)

        self.response_unauthorized(response)

    def test_get_user_infos_inactive_user(self):
        """
        Test that inactive users cannot access user information.
        """

        with tenant_context(self.tenant):
            self.user.is_active = False
            self.user.save()

        url = reverse("user")
        response = self.client.get(url, user=self.user)
        self.response_unauthorized(response)
