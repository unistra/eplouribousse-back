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


class ProjectCreatorViewTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.user = User.objects.create_user(email="username@eplouribousse.fr")
            self.superuser = User.objects.create_superuser(email="admin@eplouribousse.fr")

    @parameterized.expand(
        [
            (Role.TENANT_SUPER_USER, True, status.HTTP_201_CREATED),
            (Role.PROJECT_CREATOR, False, status.HTTP_403_FORBIDDEN),
            (Role.INSTRUCTOR, False, status.HTTP_403_FORBIDDEN),
            (Role.PROJECT_ADMIN, False, status.HTTP_403_FORBIDDEN),
            (Role.PROJECT_MANAGER, False, status.HTTP_403_FORBIDDEN),
            (Role.CONTROLLER, False, status.HTTP_403_FORBIDDEN),
            (Role.GUEST, False, status.HTTP_403_FORBIDDEN),
            (None, False, status.HTTP_403_FORBIDDEN),
        ]
    )
    def test_assign_project_creator_permissions(self, role, should_succeed, expected_status):
        user = UserWithRoleFactory(role=role, project=ProjectFactory(), library=LibraryFactory())
        response = self.post(
            reverse("user-project-creator", kwargs={"pk": self.user.id}),
            user=user,
        )
        self.assertEqual(response.status_code, expected_status)
        if should_succeed:
            self.assertTrue(response.data["is_project_creator"])
            self.assertTrue(self.user.is_project_creator)
        else:
            self.response_forbidden(response)

    @parameterized.expand(
        [
            (Role.TENANT_SUPER_USER, True, status.HTTP_204_NO_CONTENT),
            (Role.PROJECT_CREATOR, False, 403),
            (Role.INSTRUCTOR, False, 403),
            (Role.PROJECT_ADMIN, False, 403),
            (Role.PROJECT_MANAGER, False, 403),
            (Role.CONTROLLER, False, 403),
            (Role.GUEST, False, 403),
            (None, False, 403),
        ]
    )
    def test_unassign_project_creator_permissions(self, role, should_succeed, expected_status):
        user = UserWithRoleFactory(role=role, project=ProjectFactory(), library=LibraryFactory())
        # first, assign the user as a project creator
        response = self.post(
            reverse("user-project-creator", kwargs={"pk": self.user.id}),
            user=self.superuser,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # then, try to unassign the user

        response = self.delete(
            reverse("user-project-creator", kwargs={"pk": self.user.id}),
            user=user,
        )
        self.assertEqual(response.status_code, expected_status)
        if should_succeed:
            self.assertFalse(response.data["is_project_creator"])
            self.assertFalse(self.user.is_project_creator)
        else:
            self.response_forbidden(response)


class TenantSuperUserViewTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.user = User.objects.create_user(email="user@eplouribousse.fr")
            self.superuser = User.objects.create_superuser(email="admin@eplouribousse", is_superuser=True)

    @parameterized.expand(
        [
            (Role.TENANT_SUPER_USER, True, status.HTTP_201_CREATED),
            (Role.PROJECT_CREATOR, False, status.HTTP_403_FORBIDDEN),
            (Role.INSTRUCTOR, False, status.HTTP_403_FORBIDDEN),
            (Role.PROJECT_ADMIN, False, status.HTTP_403_FORBIDDEN),
            (Role.PROJECT_MANAGER, False, status.HTTP_403_FORBIDDEN),
            (Role.CONTROLLER, False, status.HTTP_403_FORBIDDEN),
            (Role.GUEST, False, status.HTTP_403_FORBIDDEN),
            (None, False, status.HTTP_403_FORBIDDEN),
        ]
    )
    def test_assign_tenant_superuser_permissions(self, role, should_succeed, expected_status):
        user = UserWithRoleFactory(role=role, project=ProjectFactory(), library=LibraryFactory())
        response = self.post(
            reverse("user-superuser", kwargs={"pk": self.user.id}),
            user=user,
        )
        self.user.refresh_from_db()
        self.assertEqual(response.status_code, expected_status)
        if should_succeed:
            self.assertTrue(response.data["is_superuser"])
            self.assertTrue(self.user.is_superuser)
        else:
            self.response_forbidden(response)

    def test_there_must_remain_at_least_one_tenant_superuser(self):
        # try to unassign the only tenant superuser
        response = self.delete(
            reverse("user-superuser", kwargs={"pk": self.superuser.id}),
            user=self.superuser,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("There must remain at least one superuser", str(response.data[0]))
