from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context

from epl.apps.project.models import Project
from epl.apps.user.models import User
from epl.tests import TestCase


class ProjectCreatorViewTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.user = User.objects.create_user(email="username@eplouribousse.fr")
            self.superuser = User.objects.create_superuser(email="admin@eplouribousse.fr")
            self.project = Project.objects.create(name="project")

    def test_project_creator(self):
        response = self.get(reverse("user_profile"), user=self.user)
        self.response_ok(response)
        self.assertFalse(response.data["is_project_creator"])

    def test_set_project_creator(self):
        response = self.post(
            reverse("user-project-creator", kwargs={"pk": self.user.id}),
            user=self.superuser,
        )
        self.response_ok(response)
        self.assertTrue(response.data["is_project_creator"])
        self.assertTrue(self.user.is_project_creator)

    def test_unassign_project_creator(self):
        response = self.delete(
            reverse("user-project-creator", kwargs={"pk": self.user.id}),
            user=self.superuser,
        )
        self.response_ok(response)
        self.assertFalse(response.data["is_project_creator"])
        self.assertFalse(self.user.is_project_creator)

    def test_must_be_superuser_to_assign_project_creator(self):
        response = self.post(
            reverse("user-project-creator", kwargs={"pk": self.user.id}),
            user=self.user,
        )
        self.response_forbidden(response)
