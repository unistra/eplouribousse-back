from urllib.parse import urlencode

from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context

from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import UserFactory
from epl.apps.user.models import User
from epl.tests import TestCase


# todo: implement access control in project creation
class ProjectCreationTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.user = User.objects.create_user(email="test_user@eplouribousse.fr")

    def test_create_project_success(self):
        data = {
            "name": "New Project",
            "description": "This is a test project.",
        }
        response = self.post(reverse("project-list"), data=data, content_type="application/json", user=self.user)
        self.response_created(response)
        self.assertEqual(response.data["name"], data["name"])
        self.assertEqual(response.data["description"], data["description"])

    def test_collection_default_exclusion_reasons_set_at_project_creation(self):
        data = {
            "name": "New Project",
            "description": "This is a test project.",
        }
        response = self.post(reverse("project-list"), data=data, content_type="application/json", user=self.user)
        self.response_created(response)
        self.assertIn("exclusion_reasons", response.data["settings"])
        self.assertCountEqual(
            response.data["settings"]["exclusion_reasons"],
            ["Participation in another project", "Incorrect assignment", "Other"],
        )


class ExclusionReasonsTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.user = UserFactory(email="<EMAIL>")
            self.project = ProjectFactory(name="Test Project")

    def test_add_exclusion_reason_success(self):
        """Test successful addition of a new exclusion reason"""
        data = {"exclusion_reason": "New exclusion reason"}

        url = reverse("project-exclusion-reason", kwargs={"pk": self.project.pk})
        response = self.post(url, data=data, content_type="application/json", user=self.user)

        self.response_created(response)
        self.project.refresh_from_db()
        self.assertIn("New exclusion reason", self.project.settings["exclusion_reasons"])
        self.assertEqual(len(self.project.settings["exclusion_reasons"]), 4)

    def test_add_exclusion_reason_duplicate(self):
        """Adding a duplicate exclusion reason should not raise an error"""
        data = {"exclusion_reason": "Other"}
        url = reverse("project-exclusion-reason", kwargs={"pk": self.project.pk})
        response = self.post(url, data=data, content_type="application/json", user=self.user)
        self.response_created(response)
        self.assertIn("Other", self.project.settings["exclusion_reasons"])
        self.assertEqual(len(self.project.settings["exclusion_reasons"]), 3)

    def test_add_exclusion_reason_empty_string(self):
        data = {"exclusion_reason": ""}
        url = reverse("project-exclusion-reason", kwargs={"pk": self.project.pk})
        response = self.post(url, data=data, content_type="application/json", user=self.user)
        self.response_bad_request(response)
        self.assertEqual(len(self.project.settings["exclusion_reasons"]), 3)

    def test_add_exclusion_reason_blank_string(self):
        data = {"exclusion_reason": "       "}
        url = reverse("project-exclusion-reason", kwargs={"pk": self.project.pk})
        response = self.post(url, data=data, content_type="application/json", user=self.user)
        self.response_bad_request(response)
        self.assertEqual(len(self.project.settings["exclusion_reasons"]), 3)

    def test_add_exclusion_reason_missing_field(self):
        data = {}
        url = reverse("project-exclusion-reason", kwargs={"pk": self.project.pk})
        response = self.post(url, data=data, content_type="application/json", user=self.user)
        self.response_bad_request(response)
        self.assertIn("exclusion_reason", response.data)

    def test_remove_exclusion_reason_success(self):
        data = {"exclusion_reason": "Other"}

        url = f"{reverse('project-exclusion-reason', kwargs={'pk': self.project.pk})}?{urlencode(data)}"
        data = {"exclusion_reason": "Other"}
        response = self.delete(url, data=data, user=self.user)

        self.response_no_content(response)
        self.project.refresh_from_db()
        self.assertNotIn("Other", self.project.settings["exclusion_reasons"])
        self.assertEqual(len(self.project.settings["exclusion_reasons"]), 2)

    def test_remove_exclusion_reason_not_found(self):
        data = {"exclusion_reason": "Non-existent reason"}
        url = f"{reverse('project-exclusion-reason', kwargs={'pk': self.project.pk})}?{urlencode(data)}"
        response = self.delete(url, user=self.user)
        self.response_no_content(response)
        self.project.refresh_from_db()
        self.assertEqual(len(self.project.settings["exclusion_reasons"]), 3)
