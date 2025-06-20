from django.db import IntegrityError
from django.utils.translation import gettext_lazy as _
from django_tenants.test.cases import TenantTestCase

from epl.apps.project.models.library import Library
from epl.apps.project.models.project import Project, Role, Status, UserRole
from epl.apps.user.models import User


class ProjectModelTest(TenantTestCase):
    def setUp(self):
        self.library = Library.objects.create(name="Test Library", alias="TL", code="12345")
        self.project = Project.objects.create(
            name="Test Project",
            description="A test project",
            is_private=True,
            status=Status.DRAFT,
        )
        self.project.libraries.add(self.library)

    def test_project_creation(self):
        self.assertEqual(self.project.name, "Test Project")
        self.assertEqual(self.project.status, Status.DRAFT)
        self.assertTrue(self.project.is_private)
        self.assertIn(self.library, self.project.libraries.all())

    def test_project_str(self):
        self.assertEqual(str(self.project), "Test Project")

    def test_status_constraint(self):
        with self.assertRaises(IntegrityError):
            Project.objects.create(name="Invalid Status", status=9999)


class UserRoleModelTest(TenantTestCase):
    def setUp(self):
        self.user = User.objects.create(username="user", email="user@example.com")
        self.admin = User.objects.create(username="admin", email="admin@example.com")
        self.library = Library.objects.create(name="Test Library", alias="TL", code="12345")
        self.project = Project.objects.create(name="Test Project")
        self.project.libraries.add(self.library)
        self.role = UserRole.objects.create(
            user=self.user,
            project=self.project,
            role=Role.INSTRUCTOR,
            assigned_by=self.admin,
            library=self.library,
        )

    def test_userrole_creation(self):
        self.assertEqual(self.role.user, self.user)
        self.assertEqual(self.role.project, self.project)
        self.assertEqual(self.role.role, Role.INSTRUCTOR)
        self.assertEqual(self.role.library, self.library)
        self.assertIsNotNone(self.role.assigned_at)
        self.assertEqual(self.role.assigned_by, self.admin)

    def test_userrole_str(self):
        expected = f"{self.user} - {_('Instructor')} ({self.project})"
        self.assertEqual(str(self.role), expected)

    def test_userrole_unique_constraint(self):
        with self.assertRaises(IntegrityError):
            UserRole.objects.create(user=self.user, project=self.project, role=Role.INSTRUCTOR)

    def test_userrole_role_constraint(self):
        with self.assertRaises(IntegrityError):
            UserRole.objects.create(user=self.user, project=self.project, role="invalid_role")
