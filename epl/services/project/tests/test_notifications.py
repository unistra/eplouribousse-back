from epl.apps.project.models import Project
from epl.apps.user.models import User
from epl.services.project.notifications import should_send_alert
from epl.tests import TestCase


class ShouldSendAlertTest(TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="user@eplouribousse.fr")
        self.project = Project.objects.create(name="Test Project")
        self.project_id_str = str(self.project.id)

    def test_alert_enabled_everywhere(self):
        self.project.settings = {"alerts": {"position": True}}
        self.project.save()
        self.user.settings = {"alerts": {self.project_id_str: {"position": True}}}
        self.user.save()
        self.assertTrue(should_send_alert(self.user, self.project, "position"))

    def test_alert_disabled_in_project(self):
        self.project.settings = {"alerts": {"position": False}}
        self.project.save()
        self.user.settings = {"alerts": {self.project_id_str: {"position": True}}}
        self.user.save()
        self.assertFalse(should_send_alert(self.user, self.project, "position"))

    def test_alert_enabled_in_project_but_disabled_for_user(self):
        self.project.settings = {"alerts": {"position": True}}
        self.project.save()
        self.user.settings = {"alerts": {self.project_id_str: {"position": False}}}
        self.user.save()
        self.assertFalse(should_send_alert(self.user, self.project, "position"))

    def test_alert_not_configured_anywhere(self):
        self.project.settings = {}
        self.project.save()
        self.user.settings = {}
        self.user.save()
        self.assertTrue(should_send_alert(self.user, self.project, "position"))

    def test_alert_enabled_in_project_user_has_no_settings(self):
        self.project.settings = {"alerts": {"position": True}}
        self.project.save()
        self.user.settings = {}
        self.user.save()
        self.assertTrue(should_send_alert(self.user, self.project, "position"))

    def test_alert_enabled_for_user_project_has_no_settings(self):
        self.project.settings = {}
        self.project.save()
        self.user.settings = {"alerts": {self.project_id_str: {"position": True}}}
        self.user.save()
        self.assertTrue(should_send_alert(self.user, self.project, "position"))

    def test_alert_disabled_for_user_project_has_no_settings(self):
        self.project.settings = {}
        self.project.save()
        self.user.settings = {"alerts": {self.project_id_str: {"position": False}}}
        self.user.save()
        self.assertFalse(should_send_alert(self.user, self.project, "position"))
