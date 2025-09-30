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

    def test_user_can_set_notification_preferences_for_specific_project(self):
        url = reverse("user-project-settings")
        response = self.patch(
            url,
            user=self.user,
            data={"project_id": str(self.project.id), "alert_type": "control", "enabled": True},
            content_type="application/json",
        )
        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["alert_type"], "control")
        self.assertEqual(response.data["enabled"], True)
        self.assertIn("control", self.user.settings["alerts"][str(self.project.id)])
        self.assertTrue(self.user.settings["alerts"][str(self.project.id)]["control"])

    def test_user_can_get_notification_preferences_for_specific_project(self):
        url = reverse("user-project-settings")
        response = self.get(
            url,
            user=self.user,
            data={"project_id": str(self.project.id), "alert_type": "position"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["project_id"], str(self.project.id))
        self.assertEqual(response.data["alert_type"], "position")
        self.assertTrue(response.data["enabled"])

    def test_get_alert_missing_project_id_returns_400(self):
        url = reverse("user-project-settings")
        response = self.get(
            url,
            user=self.user,
            data={"alert_type": "position"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)

    def test_get_unconfigured_alert_in_user_settings_returns_true_by_default(self):
        url = reverse("user-project-settings")
        response = self.get(
            url,
            user=self.user,
            data={"project_id": str(self.project.id), "alert_type": "not_configured"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["project_id"], str(self.project.id))
        self.assertEqual(response.data["alert_type"], "not_configured")
        self.assertTrue(response.data["enabled"])
