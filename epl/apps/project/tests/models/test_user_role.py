from django.db import IntegrityError
from django.utils.translation import gettext_lazy as _
from django_tenants.test.cases import TenantTestCase

from epl.apps.project.models import Project, Role, UserRole
from epl.apps.user.models import User


class UserRoleModelTest(TenantTestCase):
    def setUp(self):
        super().setUp()

        # Create users
        self.user1 = User.objects.create(username="user1", email="user1@example.com")
        self.user2 = User.objects.create(username="user2", email="user2@example.com")
        self.admin = User.objects.create(username="admin", email="admin@example.com")

        # Create projects
        self.project1 = Project.objects.create(name="Project 1", description="First test project")
        self.project2 = Project.objects.create(name="Project 2", description="Second test project")

        # Create roles
        self.role1 = UserRole.objects.create(
            user=self.user1, project=self.project1, role=Role.INSTRUCTOR, assigned_by=self.admin
        )
        self.role2 = UserRole.objects.create(user=self.user2, project=self.project1, role=Role.PROJECT_CREATOR)

    def test_userrole_creation(self):
        """Tests basic creation of a UserRole"""
        role = UserRole.objects.create(user=self.user1, project=self.project2, role=Role.GUEST)
        self.assertEqual(role.user, self.user1)
        self.assertEqual(role.project, self.project2)
        self.assertEqual(role.role, Role.GUEST)
        self.assertIsNotNone(role.assigned_at)
        self.assertIsNone(role.assigned_by)

    def test_userrole_str(self):
        """Tests the string representation of a UserRole"""
        expected_str = f"{self.user1} - {_('Instructor')} ({self.project1})"
        self.assertEqual(str(self.role1), expected_str)

    def test_userrole_unique_constraint(self):
        """ " A UserRole record with the same user, role, and project should not be created"""
        # Creating a UserRole with the same user, role, and project should raise an IntegrityError
        with self.assertRaises(IntegrityError):
            UserRole.objects.create(user=self.user1, project=self.project1, role=Role.INSTRUCTOR)

    def test_userrole_unique_constraint_different_users_can_have_same_role(self):
        # Creating the same role for a different user, in the same project should work
        created_role = UserRole.objects.create(
            user=self.user2,
            project=self.project1,
            role=Role.INSTRUCTOR,
        )
        # Check that the role was created successfully
        self.assertEqual(created_role.user, self.user2)
        self.assertEqual(created_role.role, Role.INSTRUCTOR)
        self.assertEqual(created_role.project, self.project1)
        # Check that the role is the same as role1
        self.assertEqual(created_role.role, self.role1.role)

    def test_userrole_unique_constraint_same_user_can_have_different_roles(self):
        created_role = UserRole.objects.create(
            user=self.user1,
            project=self.project1,
            role=Role.PROJECT_CREATOR,
        )

        # Check that the role was created successfully
        self.assertEqual(created_role.user, self.user1)
        self.assertEqual(created_role.project, self.project1)
        self.assertEqual(created_role.role, Role.PROJECT_CREATOR)
        # Check that the role is different from role1
        self.assertNotEqual(created_role.role, self.role1.role)

    def test_cascade_delete_user(self):
        """Tests that deleting a user also deletes their entries in UserRole"""
        self.user1.delete()
        with self.assertRaises(UserRole.DoesNotExist):
            UserRole.objects.get(id=self.role1.id)

    def test_cascade_delete_project(self):
        """Tests that deleting a project also deletes its entries in UserRole"""
        self.project1.delete()
        with self.assertRaises(UserRole.DoesNotExist):
            UserRole.objects.get(id=self.role1.id)

    def test_unvalid_role_cant_be_created(self):
        """Tests that an invalid role cannot be created"""
        with self.assertRaises(IntegrityError):
            UserRole.objects.create(user=self.user1, project=self.project1, role="invalid_role")

    def test_valid_role_can_be_created(self):
        """Tests that a valid role can be created"""
        user_role = UserRole.objects.create(user=self.user1, project=self.project1, role=Role.PROJECT_MANAGER)
        self.assertEqual(user_role.role, Role.PROJECT_MANAGER)
        self.assertEqual(user_role.get_role_display(), _("Project Manager"))

    def test_project_can_be_null_or_blank(self):
        """
        Tests that a UserRole can be created without a project.
        Important for roles that are not project-specific like tenant_super_user or project_creator.
        """
        user_role = UserRole.objects.create(user=self.user1, role=Role.TENANT_SUPER_USER)
        self.assertIsNone(user_role.project)
        self.assertEqual(user_role.role, Role.TENANT_SUPER_USER)
        self.assertIsNotNone(user_role.assigned_at)
