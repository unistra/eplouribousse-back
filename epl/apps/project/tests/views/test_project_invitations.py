from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context

from epl.apps.project.models import Project, Role
from epl.apps.user.models import User
from epl.tests import TestCase


class ProjectInvitationsViewTest(TestCase):
    INVITATION_1 = {"email": "invitee1@example.com", "role": Role.INSTRUCTOR.value, "library": None}
    INVITATION_2 = {"email": "invitee2@example.com", "role": Role.PROJECT_MANAGER.value, "library": None}
    INVALID_INVITATION = {"email": "not-an-email", "role": "invalid_role", "library": None}

    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.admin = User.objects.create_user(username="admin", email="admin@eplouribousse.fr")
            self.project = Project.objects.create(name="Project Invitations Test")

    def _url(self, pk):
        return reverse("project-update-invitations", kwargs={"pk": pk})

    def _patch(self, pk, data, user=None):
        return self.patch(self._url(pk), data=data, user=user, content_type="application/json")

    def test_update_invitations_success(self):
        data = {"invitations": [self.INVITATION_1, self.INVITATION_2]}
        response = self._patch(self.project.id, data, user=self.admin)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(self.project.id))
        self.assertEqual(len(response.data["invitations"]), 2)
        self.assertEqual(response.data["invitations"][0]["email"], self.INVITATION_1["email"])

    def test_update_invitations_missing_field(self):
        response = self._patch(self.project.id, {}, user=self.admin)
        self.assertEqual(response.status_code, 400)
        self.assertIn("invitations", response.data)

    def test_update_invitations_invalid_invitation(self):
        data = {"invitations": [self.INVALID_INVITATION]}
        response = self._patch(self.project.id, data, user=self.admin)
        self.assertEqual(response.status_code, 400)
        self.assertIn("invitations", response.data)

    def test_update_invitations_unauthorized(self):
        data = {"invitations": [self.INVITATION_1]}
        response = self._patch(self.project.id, data)
        self.assertEqual(response.status_code, 401)

    def test_update_invitations_project_not_found(self):
        data = {"invitations": [self.INVITATION_1]}
        response = self._patch(999999, data, user=self.admin)
        self.assertEqual(response.status_code, 404)
