from django.urls import reverse

from epl.apps.project.models import Project
from epl.apps.user.models import User
from epl.tests import TestCase


class ProjectAlertSettingsViewSetTest(TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="user@eplouribousse.fr")
        self.project = Project.objects.create(name="Test Project")
        self.project.settings = {
            "alerts": {
                "results": True,
                "positioning": False,
            }
        }
        self.project.save()

    def test_retrieve_alert_settings(self):
        url = reverse("project-alerts", args=[self.project.id])
        response = self.get(url, user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertIn("alerts", response.data)
        self.assertEqual(response.data["alerts"]["results"], True)
        self.assertEqual(response.data["alerts"]["positioning"], False)

    def test_update_alert_settings(self):
        url = reverse("project-alerts", args=[self.project.id])
        data = {
            "alerts": {
                "results": False,
                "positioning": True,
                "new_alert": True,
            }
        }
        response = self.patch(url, user=self.user, data=data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.settings["alerts"]["results"], False)
        self.assertEqual(self.project.settings["alerts"]["positioning"], True)
        self.assertEqual(self.project.settings["alerts"]["new_alert"], True)
