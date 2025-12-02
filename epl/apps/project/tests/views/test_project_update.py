from django_tenants.urlresolvers import reverse
from parameterized import parameterized

from epl.apps.project.models import Role
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class ProjectUpdateTest(TestCase):
    @parameterized.expand(
        [
            (Role.PROJECT_CREATOR, True, 200),
            (Role.INSTRUCTOR, False, 403),
            (Role.PROJECT_ADMIN, False, 403),
            (Role.PROJECT_MANAGER, False, 403),
            (Role.CONTROLLER, False, 403),
            (Role.GUEST, False, 403),
            (None, False, 403),
        ]
    )
    def test_update_project(self, role, should_succeed, expected_status):
        project = ProjectFactory()
        library = LibraryFactory()
        user = UserWithRoleFactory(role=role, project=project, library=library)
        data = {"name": "My Test Project", "description": "This is a test description"}

        response = self.patch(
            reverse("project-detail", args=[project.pk]), data=data, user=user, content_type="application/json"
        )

        self.assertEqual(response.status_code, expected_status)

        if should_succeed:
            self.assertEqual(response.data["name"], data["name"])
            self.assertEqual(response.data["description"], data["description"])
