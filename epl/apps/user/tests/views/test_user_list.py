from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context

from epl.apps.user.models import User
from epl.tests import TestCase


class UserListTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            for i in range(10):
                User.objects.create_user(email=f"u_{i}@eplouribousse.fr")
            User.objects.create_user(email="inactive@eplouribousse.fr", is_active=False)
            self.user = User.objects.create_user(email="user@eplouribousse.fr")

    def test_user_must_be_authenticated(self):
        response = self.get(reverse("list_users"))
        self.response_unauthorized(response)

    def test_list_users(self):
        response = self.get(reverse("list_users"), user=self.user)
        self.response_ok(response)
        self.assertEqual(response.data["count"], 11)

    def test_inactive_user_is_not_returned(self):
        response = self.get(reverse("list_users"), user=self.user, data={"page_size": 20})
        self.response_ok(response)
        self.assertEqual(response.data["count"], 11)
        self.assertNotIn("inactive@eplouribousse.fr", [user["email"] for user in response.data["results"]])

    def test_search_user(self):
        response = self.get(reverse("list_users"), user=self.user, data={"search": "user@eplouribousse.fr"})
        self.response_ok(response)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["email"], "user@eplouribousse.fr")

    def test_search_does_not_return_inactive_user(self):
        response = self.get(reverse("list_users"), user=self.user, data={"search": "inactive@eplouribousse.fr"})
        self.response_ok(response)
        self.assertEqual(response.data["count"], 0)
