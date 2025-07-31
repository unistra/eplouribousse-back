from urllib.parse import urlencode

from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context
from parameterized import parameterized

from epl.apps.project.models import Role
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import ProjectCreatorFactory, UserFactory, UserWithRoleFactory
from epl.tests import TestCase


class ProjectCreationTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.user = ProjectCreatorFactory()
            self.project = ProjectFactory()
            self.library = LibraryFactory()

    @parameterized.expand(
        [
            (Role.PROJECT_CREATOR, True, 201),
            (Role.INSTRUCTOR, False, 403),
            (Role.PROJECT_ADMIN, False, 403),
            (Role.PROJECT_MANAGER, False, 403),
            (Role.CONTROLLER, False, 403),
            (Role.GUEST, False, 403),
            (None, False, 403),
        ]
    )
    def test_project_creation_permissions(self, role, should_succeed, expected_status):
        user = UserWithRoleFactory(role=role, project=self.project, library=self.library)
        data = {
            "name": "New Project",
            "description": "This is a test project.",
        }
        response = self.post(reverse("project-list"), data=data, content_type="application/json", user=user)
        self.assertEqual(response.status_code, expected_status)

        if should_succeed:
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
            self.user = ProjectCreatorFactory()
            self.project = ProjectFactory(name="Test Project")

    def test_project_admin_can_add_exclusion_reason(self):
        with tenant_context(self.tenant):
            admin = UserFactory()
            admin.project_roles.create(project=self.project, role=Role.PROJECT_ADMIN, assigned_by=self.user)

        data = {"exclusion_reason": "New exclusion reason"}
        url = reverse("project-exclusion-reason", kwargs={"pk": self.project.pk})
        response = self.post(url, data=data, content_type="application/json", user=self.user)
        self.response_created(response)

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
