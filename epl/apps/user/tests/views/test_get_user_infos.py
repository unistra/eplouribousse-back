from django.urls import reverse
from django_tenants.utils import tenant_context

from epl.apps.project.tests.factories.user import UserFactory
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
        url = reverse("user-profile")
        response = self.get(url, user=self.user)

        self.response_ok(response)
        self.assertEqual(response.data["username"], self.user.username)

    def test_get_user_infos_unauthenticated(self):
        """
        Test that unauthenticated users cannot access user information.
        """
        url = reverse("user_profile")
        response = self.client.get(url)

        self.response_unauthorized(response)

    def test_get_user_infos_inactive_user(self):
        """
        Test that inactive users cannot access user information.
        """

        with tenant_context(self.tenant):
            self.user.is_active = False
            self.user.save()

        url = reverse("user_profile")
        response = self.client.get(url, user=self.user)
        self.response_unauthorized(response)


class UpdateUserProfileTest(TestCase):
    def setUp(self):
        """
        Set up the test case.
        """
        super().setUp()  # Initialize client and tenant
        self.user = UserFactory(
            first_name="Firstname",
            last_name="Lastname",
            settings={"theme": "light", "locale": "en"},
        )

    def test_update_firstname_and_lastname(self):
        response = self.patch(
            reverse("user_profile"),
            content_type="application/json",
            data={"first_name": "NewFirstname", "last_name": "NewLastname"},
            user=self.user,
        )
        self.response_ok(response)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "NewFirstname")
        self.assertEqual(self.user.last_name, "NewLastname")

    def test_update_settings(self):
        response = self.patch(
            reverse("user_profile"),
            content_type="application/json",
            data={"settings": {"theme": "dark", "locale": "fr"}},
            user=self.user,
        )
        self.response_ok(response)
        self.user.refresh_from_db()
        self.assertEqual(self.user.settings["theme"], "dark")
        self.assertEqual(self.user.settings["locale"], "fr")
