from django.db import IntegrityError
from django.utils.translation import gettext_lazy as _
from django_tenants.test.cases import TenantTestCase

from epl.apps.project.models.library import Library
from epl.apps.project.models.project import Project, ProjectLibrary, Role, Status, UserRole
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


class ProjectLibraryModelTest(TenantTestCase):
    def setUp(self):
        self.library1 = Library.objects.create(name="Lib1", alias="L1", code="001")
        self.library2 = Library.objects.create(name="Lib2", alias="L2", code="002")
        self.project = Project.objects.create(name="Project1")
        self.project2 = Project.objects.create(name="Project2")

    def test_str(self):
        pl = ProjectLibrary.objects.create(
            project=self.project, library=self.library1, is_alternative_storage_site=True
        )
        expected = f"{self.project.name} - {self.library1.name} {_('Alternative storage site')}"
        self.assertEqual(str(pl), expected)

        pl2 = ProjectLibrary.objects.create(
            project=self.project, library=self.library2, is_alternative_storage_site=False
        )
        expected2 = f"{self.project.name} - {self.library2.name} "
        self.assertEqual(str(pl2), expected2)

    def test_unique_constraint(self):
        ProjectLibrary.objects.create(project=self.project, library=self.library1, is_alternative_storage_site=False)
        with self.assertRaises(IntegrityError):
            ProjectLibrary.objects.create(project=self.project, library=self.library1, is_alternative_storage_site=True)

    def test_multiple_alternative_storage_sites(self):
        pl1 = ProjectLibrary.objects.create(
            project=self.project, library=self.library1, is_alternative_storage_site=True
        )
        pl2 = ProjectLibrary.objects.create(
            project=self.project, library=self.library2, is_alternative_storage_site=True
        )
        self.assertTrue(pl1.is_alternative_storage_site)
        self.assertTrue(pl2.is_alternative_storage_site)
