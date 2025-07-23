from django_tenants.utils import tenant_context

from epl.apps.project.models import Role, UserRole
from epl.apps.user.models import User
from epl.tests import TestCase


class TestUser(TestCase):
    def test_user_str_with_first_and_last_name(self):
        user = User.objects.create_user(
            "test_user", first_name="First", last_name="Last", email="first.last@example.com"
        )
        self.assertEqual(
            str(user),
            "First Last",
        )

    def test_user_with_first_name_only(self):
        user = User.objects.create_user("test_user", first_name="First", email="first.last@example.com")
        self.assertEqual(
            str(user),
            "First",
        )

    def test_user_with_last_name_only(self):
        user = User.objects.create_user("test_user", last_name="Last", email="first.last@example.com")
        self.assertEqual(
            str(user),
            "Last",
        )

    def test_user_str_with_no_first_or_last_name(self):
        user = User.objects.create_user("test_user", email="first.last@example.com")
        self.assertEqual(
            str(user),
            "test_user",
        )


class IsProjectCreatorTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.user = User.objects.create_user(email="first.last@example.com")

    def test_user_is_not_project_creator_by_default(self):
        self.assertFalse(self.user.is_project_creator)

    def test_set_user_is_project_creator(self):
        self.user.set_is_project_creator(True, assigned_by=self.user)
        self.assertTrue(self.user.is_project_creator)

    def test_set_user_is_project_creator_creates_userrole(self):
        self.user.set_is_project_creator(True, assigned_by=self.user)
        self.assertTrue(UserRole.objects.filter(user=self.user, role=Role.PROJECT_CREATOR).exists())

    def test_remove_user_is_project_creator_role(self):
        self.user.set_is_project_creator(False, assigned_by=self.user)
        self.assertFalse(self.user.is_project_creator)
        self.assertFalse(UserRole.objects.filter(user=self.user, role=Role.PROJECT_CREATOR).exists())


class TestUserManager(TestCase):
    def test_create_user_requires_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user("test_user")

    def test_missing_username_uses_email_as_username(self):
        user = User.objects.create_user(email="first.last@example.com")
        user.refresh_from_db()
        self.assertEqual(user.username, "first.last@example.com")

    def test_create_user_does_not_set_is_superuser(self):
        user = User.objects.create_user(email="first.last@example.com")
        user.refresh_from_db()
        self.assertFalse(user.is_superuser)

    def test_create_user_does_not_set_is_staff(self):
        user = User.objects.create_user(email="first.last@example.com")
        user.refresh_from_db()
        self.assertFalse(user.is_staff)

    def test_create_superuser_requires_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser("test_user")

    def test_missing_username_creates_superuser_with_email_as_username(self):
        user = User.objects.create_superuser(email="first.last@example.com")
        user.refresh_from_db()
        self.assertEqual(user.username, "first.last@example.com")

    def test_create_superuser_sets_is_superuser(self):
        user = User.objects.create_superuser(email="first.last@example.com")
        user.refresh_from_db()
        self.assertTrue(user.is_superuser)

    def test_create_superuser_sets_is_staff(self):
        user = User.objects.create_superuser(email="first.last@example.com")
        user.refresh_from_db()
        self.assertTrue(user.is_staff)


class IsInstructorForTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            from epl.apps.project.models import Library, Project

            self.user = User.objects.create_user(email="instructor@example.com")
            self.other_user = User.objects.create_user(email="other@example.com")
            self.assigner = User.objects.create_user(email="assigner@example.com")

            self.project1 = Project.objects.create(name="Test Project 1", description="Test project description")
            self.project2 = Project.objects.create(name="Test Project 2", description="Another test project")

            self.library1 = Library.objects.create(name="Library 1", alias="LIB1", code="LIB001")
            self.library2 = Library.objects.create(name="Library 2", alias="LIB2", code="LIB002")

            self.project1.libraries.add(self.library1, self.library2)
            self.project2.libraries.add(self.library1)

    def test_user_is_instructor_for_specific_project_and_library(self):
        UserRole.objects.create(
            user=self.user,
            role=Role.INSTRUCTOR,
            project=self.project1,
            library=self.library1,
            assigned_by=self.assigner,
        )
        self.assertTrue(self.user.is_instructor(self.project1, self.library1))

    def test_user_is_not_instructor_for_different_project(self):
        UserRole.objects.create(
            user=self.user,
            role=Role.INSTRUCTOR,
            project=self.project1,
            library=self.library1,
            assigned_by=self.assigner,
        )
        self.assertFalse(self.user.is_instructor(self.project2, self.library1))

    def test_user_is_not_instructor_for_different_library(self):
        UserRole.objects.create(
            user=self.user,
            role=Role.INSTRUCTOR,
            project=self.project1,
            library=self.library1,
            assigned_by=self.assigner,
        )
        self.assertFalse(self.user.is_instructor(self.project1, self.library2))

    def test_user_is_not_instructor_with_different_role(self):
        UserRole.objects.create(
            user=self.user,
            role=Role.PROJECT_ADMIN,
            project=self.project1,
            library=self.library1,
            assigned_by=self.assigner,
        )
        self.assertFalse(self.user.is_instructor(self.project1, self.library1))
