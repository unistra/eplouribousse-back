from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context

from epl.apps.project.models.library import Library
from epl.apps.user.models import User
from epl.tests import TestCase


class LibraryViewsTest(TestCase):
    def setUp(self):
        super().setUp()

        with tenant_context(self.tenant):
            # Create a user
            self.user = User.objects.create_user(username="user", email="user@eplouribouse.fr")
            self.library = Library.objects.create(
                name="Bibliothèque Nationale de Test",
                alias="BNT",
                code="67000",
            )

    def test_get_library_list(self):
        url = reverse("library-list")

        response = self.get(url, user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data.get("results")), 1)
        self.assertEqual(response.data["results"][0]["name"], self.library.name)
