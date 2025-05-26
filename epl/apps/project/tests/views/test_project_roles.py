from django_tenants.urlresolvers import reverse

from epl.apps.project.models import Project, ProjectRole, UserRole
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
            role=ProjectRole.PROJECT_MANAGER,
            assigned_by=admin,
        )
        UserRole.objects.create(
            user=instructor,
            project=project_one,
            role=ProjectRole.INSTRUCTOR,
            assigned_by=admin,
        )

        project_two = Project.objects.create(name="Project Two")
        UserRole.objects.create(
            user=manager,
            project=project_two,
            role=ProjectRole.PROJECT_ADMIN,
            assigned_by=admin,
        )
        UserRole.objects.create(
            user=manager,
            project=project_two,
            role=ProjectRole.INSTRUCTOR,
            assigned_by=admin,
        )

        response = self.get(reverse("project-users", kwargs={"pk": project_one.id}), user=admin)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        response = self.get(reverse("project-users", kwargs={"pk": project_two.id}), user=admin)
        self.response_ok(response)
        self.assertListEqual(
            sorted(response.data[0]["roles"]),
            sorted([ProjectRole.PROJECT_ADMIN.value, ProjectRole.INSTRUCTOR.value]),
        )
