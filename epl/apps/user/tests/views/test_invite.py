import json

from django.utils.translation import gettext as _
from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context
from parameterized import parameterized
from rest_framework import status

from epl.apps.project.models import Role
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.apps.user.models import User
from epl.tests import TestCase


class TestInviteView(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.project = ProjectFactory()
            self.library = LibraryFactory()

    @parameterized.expand(
        [
            (Role.TENANT_SUPER_USER, 200),
            (Role.PROJECT_CREATOR, 403),
            (Role.INSTRUCTOR, 403),
            (Role.PROJECT_ADMIN, 403),
            (Role.PROJECT_MANAGER, 403),
            (Role.CONTROLLER, 403),
            (Role.GUEST, 403),
            (None, 403),
        ]
    )
    def test_invite_permissions(self, role, expected_status):
        user = UserWithRoleFactory(role=role, project=self.project, library=self.library)
        response = self.post(reverse("invite"), {"email": "new_user@example.com"}, user=user)
        self.assertEqual(response.status_code, expected_status)

    def test_invite_unauthenticated_access_forbidden(self):
        response = self.client.post(
            reverse("invite"), {"email": "new_user@example.com"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invite_with_existing_email(self):
        with tenant_context(self.tenant):
            tenant_super_user = UserWithRoleFactory(role=Role.TENANT_SUPER_USER)
            User.objects.create_user(email="existing@example.com")

        response = self.post(reverse("invite"), {"email": "existing@example.com"}, user=tenant_super_user)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = json.loads(response.content.decode())
        self.assertIn(str(_("Email is already linked to an account")), data["nonFieldErrors"][0])

    def test_invite_with_invalid_email(self):
        with tenant_context(self.tenant):
            tenant_super_user = UserWithRoleFactory(role=Role.TENANT_SUPER_USER)

        response = self.post(reverse("invite"), {"email": "not-an-email"}, user=tenant_super_user)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
