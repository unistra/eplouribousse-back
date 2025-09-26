from django.urls import reverse
from parameterized import parameterized

from epl.apps.project.models import Role
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class ProjectAlertSettingsViewSetTest(TestCase):
    def test_retrieve_alert_settings(self):
        project = ProjectFactory()
        project.settings = {"alerts": {"results": True, "positioning": False}}
        project.save()
        library = LibraryFactory()
        user = UserWithRoleFactory(role=Role.PROJECT_ADMIN, project=project, library=library)
        url = reverse("project-alerts", args=[project.id])
        response = self.get(url, user=user)
        self.assertEqual(response.status_code, 200)
        self.assertIn("alerts", response.data)
        self.assertEqual(response.data["alerts"]["results"], True)
        self.assertEqual(response.data["alerts"]["positioning"], False)

    @parameterized.expand(
        [
            (Role.PROJECT_CREATOR, False, 403),
            (Role.INSTRUCTOR, False, 403),
            (Role.PROJECT_ADMIN, True, 200),
            (Role.PROJECT_MANAGER, False, 403),
            (Role.CONTROLLER, False, 403),
            (Role.GUEST, False, 403),
            (None, False, 403),
        ]
    )
    def test_update_alert_settings_roles(self, role, should_succeed, expected_status):
        project = ProjectFactory()
        project.settings = {"alerts": {"results": True, "positioning": False}}
        project.save()
        library = LibraryFactory()
        user = UserWithRoleFactory(role=role, project=project, library=library)
        url = reverse("project-alerts", args=[project.id])
        data = {
            "alerts": {
                "results": False,
                "positioning": True,
                "new_alert": True,
            }
        }
        response = self.patch(url, user=user, data=data, content_type="application/json")
        self.assertEqual(response.status_code, expected_status)
        project.refresh_from_db()
        if should_succeed:
            self.assertEqual(project.settings["alerts"]["results"], False)
            self.assertEqual(project.settings["alerts"]["positioning"], True)
            self.assertEqual(project.settings["alerts"]["new_alert"], True)
        else:
            self.assertNotEqual(project.settings["alerts"].get("results"), False)
