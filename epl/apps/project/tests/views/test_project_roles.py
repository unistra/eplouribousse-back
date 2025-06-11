from urllib.parse import urlencode

from django_tenants.urlresolvers import reverse

from epl.apps.project.models import Library, Project, Role, UserRole
from epl.apps.user.models import User
from epl.tests import TestCase


class ProjectRolesTest(TestCase):
    def test_list_project_users_with_roles(self):
        manager = User.objects.create_user(email="manager@eplouribousse.fr")
        instructor = User.objects.create_user(email="instructor@eplouribousse.fr")
        admin = User.objects.create_user(email="admin@eplouribousse.fr")

        project_one = Project.objects.create(name="Project One")
        UserRole.objects.create(
            user=manager,
            project=project_one,
            role=Role.PROJECT_MANAGER,
            assigned_by=admin,
        )
        UserRole.objects.create(
            user=instructor,
            project=project_one,
            role=Role.INSTRUCTOR,
            assigned_by=admin,
        )

        project_two = Project.objects.create(name="Project Two")
        UserRole.objects.create(
            user=manager,
            project=project_two,
            role=Role.PROJECT_ADMIN,
            assigned_by=admin,
        )
        UserRole.objects.create(
            user=manager,
            project=project_two,
            role=Role.INSTRUCTOR,
            assigned_by=admin,
        )

        response = self.get(reverse("project-users", kwargs={"pk": project_one.id}), user=admin)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        response = self.get(reverse("project-users", kwargs={"pk": project_two.id}), user=admin)
        self.response_ok(response)
        self.assertListEqual(
            sorted(response.data[0]["roles"]),
            sorted([Role.PROJECT_ADMIN.value, Role.INSTRUCTOR.value]),
        )


class ProjectAssignRoleTest(TestCase):
    def setUp(self):
        super().setUp()
        self.user_one = User.objects.create_user(email="user_1@eplouribousse.fr")
        self.user_two = User.objects.create_user(email="user_2@eplouribousse.fr")
        self.admin = User.objects.create_user(email="admin@eplouribousse.fr")

        self.library_one = Library.objects.create(name="Library One", alias="Lib1", code="001")
        self.library_two = Library.objects.create(name="Library Two", alias="Lib2", code="002")

        self.project_one = Project.objects.create(name="Project One")
        self.project_two = Project.objects.create(name="Project Two")

    def test_assign_role_and_library_to_user_in_project(self):
        data = {
            "role": Role.INSTRUCTOR.value,
            "user_id": self.user_one.id,
            "library_id": self.library_one.id,
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.user_one,
        )

        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["role"], data["role"])
        self.assertEqual(response.data["user_id"], str(self.user_one.id))
        self.assertEqual(response.data["library_id"], str(self.library_one.id))

    def test_assign_role_without_library(self):
        data = {
            "role": Role.PROJECT_MANAGER.value,
            "user_id": self.user_one.id,
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.user_one,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["role"], data["role"])

    def test_assign_role_to_nonexistent_user(self):
        data = {
            "role": Role.INSTRUCTOR.value,
            "user_id": 99999,
            "library_id": self.library_one.id,
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.user_one,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("user_id", response.data)

    def test_assign_role_with_nonexistent_library(self):
        data = {
            "role": Role.INSTRUCTOR.value,
            "user_id": self.user_one.id,
            "library_id": 99999,  # ID qui n'existe pas
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.user_one,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("library_id", response.data)

    def test_assign_invalid_role(self):
        data = {
            "role": "INVALID_ROLE",
            "user_id": self.user_one.id,
            "library_id": self.library_one.id,
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.user_one,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.data)

    def test_assign_duplicate_role(self):
        # First assignment
        data = {
            "role": Role.INSTRUCTOR.value,
            "user_id": self.user_one.id,
            "library_id": self.library_one.id,
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.user_one,
        )
        self.assertEqual(response.status_code, 201)

        # Attempt to assign the same role again
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.user_one,
        )

        self.assertEqual(response.status_code, 201)

    def test_assign_role_missing_required_role_field(self):
        data = {
            "user_id": self.user_one.id,
            "library_id": self.library_one.id,
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.user_one,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.data)

    def test_assign_role_missing_required_user_id_field(self):
        data = {
            "role": Role.INSTRUCTOR.value,
            "library_id": self.library_one.id,
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.user_one,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("user_id", response.data)

    def test_assign_role_to_nonexistent_project(self):
        data = {
            "role": Role.INSTRUCTOR.value,
            "user_id": self.user_one.id,
            "library_id": self.library_one.id,
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": 99999}),
            data=data,
            user=self.user_one,
        )
        self.assertEqual(response.status_code, 404)

    def test_assign_different_roles_same_user_same_library(self):
        # First role assignment
        UserRole.objects.create(
            user=self.user_one,
            project=self.project_one,
            role=Role.INSTRUCTOR,
            library=self.library_one,
        )

        # Second role, same user, same library
        data = {
            "role": Role.CONTROLLER.value,
            "user_id": self.user_one.id,
            "library_id": self.library_one.id,
            "project_id": self.project_one.id,
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.user_one,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(UserRole.objects.count(), 2)

    def test_remove_role_from_user_in_project(self):
        # Create a role for the user in the project
        UserRole.objects.create(
            user=self.user_one,
            project=self.project_one,
            role=Role.INSTRUCTOR,
            library=self.library_one,
        )
        print(f"User roles: {UserRole.objects.all()}")

        # Remove the role
        data = {
            "role": Role.INSTRUCTOR.value,
            "user_id": self.user_one.id,
            "library_id": self.library_one.id,
        }
        url = f"{reverse('project-assign-roles', kwargs={'pk': self.project_one.id})}?{urlencode(data)}"
        response = self.delete(
            url,
            user=self.user_one,
        )

        print(f"Delete response status: {response.status_code}")
        print(f"Delete response data: {response.data}")
        self.assertEqual(response.status_code, 204)

        self.assertFalse(
            UserRole.objects.filter(
                user=self.user_one,
                project=self.project_one,
                role=Role.INSTRUCTOR,
                library=self.library_one,
            ).exists()
        )
