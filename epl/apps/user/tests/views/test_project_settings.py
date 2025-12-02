from django.urls import reverse
from django_tenants.utils import tenant_context

from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.user.models import User
from epl.tests import TestCase


class ProjectSettingsViewTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.user = User.objects.create_user(email="user@eplouribousse.fr")
            self.project = ProjectFactory()

            self.user.settings = {
                "alerts": {
                    str(self.project.id): {
                        "position": True,
                    },
                },
            }
            self.user.save()

    def test_user_can_get_alerts_for_specific_project(self):
        url = reverse("user-project-alerts")
        response = self.get(
            url,
            user=self.user,
            data={"project_id": str(self.project.id)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("position", response.data["alerts"])
        self.assertTrue(response.data["alerts"]["position"])

    def test_user_can_patch_alerts_for_specific_project(self):
        url = reverse("user-project-alerts")
        data = {
            "project_id": str(self.project.id),
            "alerts": {
                "control": True,
                "position": False,
            },
        }
        response = self.patch(
            url,
            user=self.user,
            data=data,
            content_type="application/json",
        )
        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["alerts"]["control"], True)
        self.assertEqual(response.data["alerts"]["position"], False)
        self.assertIn("control", self.user.settings["alerts"][str(self.project.id)])
        self.assertTrue(self.user.settings["alerts"][str(self.project.id)]["control"])
        self.assertFalse(self.user.settings["alerts"][str(self.project.id)]["position"])

    def test_get_alerts_missing_project_id_returns_400(self):
        url = reverse("user-project-alerts")
        response = self.get(
            url,
            user=self.user,
            data={},
        )
        self.assertEqual(response.status_code, 400)

    def test_get_alerts_unconfigured_project_fail(self):
        url = reverse("user-project-alerts")
        response = self.get(
            url,
            user=self.user,
            data={"project_id": "not_configured"},
        )
        self.assertEqual(response.status_code, 400)
