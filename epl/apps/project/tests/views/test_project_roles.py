from urllib.parse import urlencode

from django_tenants.urlresolvers import reverse
from parameterized import parameterized

from epl.apps.project.models import Project, Role, UserRole
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import ProjectCreatorFactory, UserFactory, UserWithRoleFactory
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
        self.user = UserFactory()
        self.project_creator = ProjectCreatorFactory()

        self.library_one = LibraryFactory()
        self.library_two = LibraryFactory()

        self.project_one = ProjectFactory()
        self.project_two = ProjectFactory()

    @parameterized.expand(
        [
            (Role.PROJECT_CREATOR, True, 201),
            (Role.INSTRUCTOR, False, 403),
            (Role.PROJECT_ADMIN, True, 201),
            (Role.PROJECT_MANAGER, False, 403),
            (Role.CONTROLLER, False, 403),
            (Role.GUEST, False, 403),
            (None, False, 403),
        ]
    )
    def test_assign_role_and_library_to_user_in_project(self, role, should_succeed, expected_status_code):
        data = {
            "role": Role.INSTRUCTOR,
            "user_id": self.user.id,
            "library_id": self.library_one.id,
        }
        user = UserWithRoleFactory(role=role, project=self.project_one, library=self.library_one)
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=user,
        )

        self.assertEqual(response.status_code, expected_status_code)

        if should_succeed:
            self.assertEqual(response.data["role"], data["role"])
            self.assertEqual(
                self.user.id, UserRole.objects.filter(project=self.project_one, role=data["role"]).first().user_id
            )
            self.assertEqual(response.data["library_id"], str(self.library_one.id))

    def test_assign_role_without_library(self):
        data = {
            "role": Role.PROJECT_MANAGER,
            "user_id": self.user.id,
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.project_creator,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["role"], data["role"])

    def test_assign_role_to_nonexistent_user(self):
        data = {
            "role": Role.INSTRUCTOR,
            "user_id": 99999,
            "library_id": self.library_one.id,
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.project_creator,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("user_id", response.data)

    def test_assign_role_with_nonexistent_library(self):
        data = {
            "role": Role.INSTRUCTOR,
            "user_id": self.user.id,
            "library_id": 99999,
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.project_creator,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("library_id", response.data)

    #
    def test_assign_invalid_role(self):
        data = {
            "role": "INVALID_ROLE",
            "user_id": self.user.id,
            "library_id": self.library_one.id,
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.project_creator,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.data)

    def test_assign_duplicate_role(self):
        data = {
            "role": Role.INSTRUCTOR,
            "user_id": self.user.id,
            "library_id": self.library_one.id,
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.project_creator,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            UserRole.objects.filter(user_id=data["user_id"], role=data["role"], library_id=data["library_id"]).count(),
            1,
        )

        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.project_creator,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            UserRole.objects.filter(user_id=data["user_id"], role=data["role"], library_id=data["library_id"]).count(),
            1,
        )

    def test_assign_role_missing_required_role_field(self):
        data = {
            "user_id": self.user.id,
            "library_id": self.library_one.id,
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.project_creator,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.data)

    def test_assign_role_missing_required_user_id_field(self):
        data = {
            "role": Role.INSTRUCTOR,
            "library_id": self.library_one.id,
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.project_creator,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("user_id", response.data)

    def test_assign_role_to_nonexistent_project(self):
        data = {
            "role": Role.INSTRUCTOR,
            "user_id": self.user.id,
            "library_id": self.library_one.id,
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": 99999}),
            data=data,
            user=self.project_creator,
        )
        self.assertEqual(response.status_code, 404)

    def test_assign_different_roles_same_user_same_library(self):
        # First role assignment
        UserRole.objects.create(
            user=self.user,
            project=self.project_one,
            role=Role.INSTRUCTOR,
            library=self.library_one,
        )

        # Second role, same user, same library
        data = {
            "role": Role.CONTROLLER,
            "user_id": self.user.id,
            "project_id": self.project_one.id,
        }
        response = self.post(
            reverse("project-assign-roles", kwargs={"pk": self.project_one.id}),
            data=data,
            user=self.project_creator,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(UserRole.objects.filter(user=self.user, project=self.project_one).count(), 2)

class ProjectRemoveRoleTest(TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.project_creator = ProjectCreatorFactory()

        self.library_one = LibraryFactory()
        self.library_two = LibraryFactory()

        self.project_one = ProjectFactory()
        self.project_two = ProjectFactory()

    @parameterized.expand(
        [
            (Role.PROJECT_CREATOR, True, 204),
            (Role.INSTRUCTOR, False, 403),
            (Role.PROJECT_ADMIN, True, 204),
            (Role.PROJECT_MANAGER, False, 403),
            (Role.CONTROLLER, False, 403),
            (Role.GUEST, False, 403),
            (None, False, 403),
        ]
    )
    def test_remove_role_to_user_in_project(self, role, should_succeed, expected_status_code):
        user = UserWithRoleFactory(role=role, project=self.project_one, library=self.library_one)
        UserRole.objects.create(
            user=self.user,
            project=self.project_one,
            role=Role.INSTRUCTOR,
            library=self.library_one,
        )
        data = {
            "role": Role.INSTRUCTOR,
            "user_id": self.user.id,
            "library_id": self.library_one.id,
        }
        url = reverse("project-assign-roles", kwargs={"pk": self.project_one.id})
        params = f"?role={data['role']}&user_id={data['user_id']}&library_id={data['library_id']}"
        response = self.delete(url + params, user=user)

        self.assertEqual(response.status_code, expected_status_code)

        if should_succeed:
            self.assertIsNone(
                UserRole.objects.filter(
                    user_id=data["user_id"],
                    role=data["role"],
                    library_id=data["library_id"],
                    project=self.project_one,
                ).first()
            )
        else:
            self.assertIsNotNone(
                UserRole.objects.filter(
                    user_id=data["user_id"],
                    role=data["role"],
                    library_id=data["library_id"],
                    project=self.project_one,
                ).first()
            )
