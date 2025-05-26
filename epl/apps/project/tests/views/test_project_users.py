import uuid

from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context

from epl.apps.project.models import Project, ProjectRole
from epl.apps.user.models import User
from epl.tests import TestCase


class ProjectUsersTest(TestCase):
    def setUp(self):
        """
        Set up the test case.
        """
        super().setUp()
        with tenant_context(self.tenant):
            # Create an admin user
            self.admin = User.objects.create_user(username="admin", email="admin@eplouribousse.fr")

            # Create a user
            self.user = User.objects.create_user(username="user", email="user@eplouribouse.fr")
            # Create projects
            self.project_one = Project.objects.create(name="Project One")
            self.project_two = Project.objects.create(name="Project Two")

            # Assign the user to projects with different roles
            self.project_one.user_roles.create(user=self.user, role=ProjectRole.PROJECT_MANAGER)
            self.project_one.user_roles.create(user=self.user, role=ProjectRole.INSTRUCTOR)

    def test_get_project_users(self):
        """
        Test the retrieval of users associated with a project."""

        url = reverse("project-users", kwargs={"pk": self.project_one.id})

        response = self.get(url, user=self.admin)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["username"], self.user.username)
        self.assertEqual(response.data[0]["roles"], ["instructor", "project_manager"])

    def test_project_not_found(self):
        """Test retrieving users for a non-existent project."""

        url = reverse("project-users", kwargs={"pk": uuid.uuid4()})
        response = self.get(url, user=self.admin, expected_status=404)

        self.response_not_found(response)


# TODO: test access control
