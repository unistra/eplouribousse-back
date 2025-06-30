from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context

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
