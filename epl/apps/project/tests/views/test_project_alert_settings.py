from django.urls import reverse
from parameterized import parameterized

from epl.apps.project.models import Role
from epl.apps.project.models.choices import AlertType
from epl.apps.project.models.project import DEFAULT_EXCLUSION_REASONS
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class ProjectAlertSettingsViewSetTest(TestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory()

        self.project.settings = {}
        self.project.settings["alerts"] = {choice[0]: False for choice in AlertType.choices}
        self.project.save()

        self.library = LibraryFactory()
        self.admin_user = UserWithRoleFactory(role=Role.PROJECT_ADMIN, project=self.project)
        self.url = reverse("project-alerts", args=[self.project.id])

    def test_admin_can_retrieve_alert_settings(self):
        expected_settings = {"alerts": {choice[0]: False for choice in AlertType.choices}}

        response = self.get(self.url, user=self.admin_user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected_settings)

    def test_admin_can_update_alert_settings(self):
        """Test that admin can update all alert settings."""

        alerts_to_update = {"alerts": {choice[0]: True for choice in AlertType.choices}}

        response = self.patch(self.url, user=self.admin_user, data=alerts_to_update, content_type="application/json")
        print(response.data)
        self.assertEqual(response.status_code, 200)

        # Verify all alerts are now True
        for alert_type in AlertType.values:
            self.assertEqual(response.data["alerts"][alert_type], True)

        # Verify in database
        self.project.refresh_from_db()
        for alert_type in AlertType.values:
            self.assertEqual(self.project.settings["alerts"][alert_type], True)

    def test_partial_update_alert_settings_fails(self):
        """Test that partial updates are not allowed."""
        alerts_to_update = {"alerts": {"edition": True, "positioning": True}}

        response = self.patch(self.url, user=self.admin_user, data=alerts_to_update, content_type="application/json")
        self.assertEqual(response.status_code, 400)

        # Le JSON Schema va rejeter car tous les champs requis ne sont pas présents
        error_message = str(response.data)
        self.assertIn("required", error_message.lower())

    def test_exclusion_reasons_are_not_updated(self):
        """Test that exclusion_reasons are preserved when updating alerts."""
        # Setup initial exclusion_reasons avec les valeurs par défaut plus une personnalisée
        initial_exclusion_reasons = [str(reason) for reason in DEFAULT_EXCLUSION_REASONS]
        self.project.settings["exclusion_reasons"] = initial_exclusion_reasons
        self.project.save()

        # Update alerts
        alerts_to_update = {"alerts": {choice[0]: True for choice in AlertType.choices}}

        response = self.patch(self.url, user=self.admin_user, data=alerts_to_update, content_type="application/json")
        self.assertEqual(response.status_code, 200)

        # Verify exclusion_reasons are preserved in database
        self.project.refresh_from_db()
        self.assertEqual(self.project.settings["exclusion_reasons"], initial_exclusion_reasons)

        # Verify exclusion_reasons are not exposed in API response
        self.assertNotIn("exclusion_reasons", response.data)

    def test_invalid_alert_type_fails(self):
        """Test that invalid alert types are rejected."""
        alerts_with_invalid_type = {
            "alerts": {
                "positioning": True,
                "arbitration": False,
                "instruction": True,
                "control": False,
                "edition": True,
                "preservation": False,
                "transfer": True,
                "invalid_type": True,  # This should cause validation to fail
            }
        }

        response = self.patch(
            self.url, user=self.admin_user, data=alerts_with_invalid_type, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

        # Le JSON Schema va rejeter car "invalid_type" n'est pas autorisé
        error_message = str(response.data)
        self.assertIn("additional", error_message.lower())

    def test_wrong_data_type_fails(self):
        """Test that wrong data types are rejected."""
        alerts_with_wrong_types = {
            "alerts": {
                "positioning": "true",  # String instead of boolean
                "arbitration": False,
                "instruction": 1,  # Integer instead of boolean
                "control": False,
                "edition": True,
                "preservation": False,
                "transfer": True,
            }
        }

        response = self.patch(
            self.url, user=self.admin_user, data=alerts_with_wrong_types, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_empty_alerts_object_fails(self):
        """Test that empty alerts object is rejected."""
        empty_alerts = {"alerts": {}}

        response = self.patch(self.url, user=self.admin_user, data=empty_alerts, content_type="application/json")
        self.assertEqual(response.status_code, 400)

        # Le JSON Schema va rejeter car les champs requis sont manquants
        error_message = str(response.data)
        self.assertIn("required", error_message.lower())

    def test_missing_alerts_field_fails(self):
        """Test that request without alerts field is rejected."""
        data_without_alerts = {"other_field": "value"}

        response = self.patch(self.url, user=self.admin_user, data=data_without_alerts, content_type="application/json")
        self.assertEqual(response.status_code, 400)


class ProjectAlertSettingsPermissionsTest(TestCase):  # Hériter de TenantTestCase au lieu de TestCase
    """Test class specifically for testing alert settings permissions."""

    def setUp(self):
        super().setUp()
        self.project = ProjectFactory()

        self.project.settings = {
            "alerts": {choice[0]: False for choice in AlertType.choices},
            "exclusion_reasons": [str(reason) for reason in DEFAULT_EXCLUSION_REASONS],
        }
        self.project.save()
        self.library = LibraryFactory()

    @parameterized.expand(
        [
            (Role.PROJECT_CREATOR, False, 403),
            (Role.INSTRUCTOR, False, 403),
            (Role.PROJECT_ADMIN, True, 200),
            (Role.PROJECT_MANAGER, False, 403),
            (Role.CONTROLLER, False, 403),
            (Role.GUEST, False, 403),
        ]
    )
    def test_update_alert_settings_permissions_by_role(self, role, should_succeed, expected_status):
        """Test that only PROJECT_ADMIN users can update alert settings."""
        user = UserWithRoleFactory(role=role, project=self.project, library=self.library)
        url = reverse("project-alerts", args=[self.project.id])

        alerts_data = {
            "alerts": {
                "positioning": True,
                "arbitration": False,
                "instruction": True,
                "control": False,
                "edition": True,
                "preservation": False,
                "transfer": True,
            }
        }

        response = self.patch(url, user=user, data=alerts_data, content_type="application/json")
        self.assertEqual(response.status_code, expected_status)
        self.project.refresh_from_db()

        if should_succeed:
            self.assertEqual(self.project.settings["alerts"]["positioning"], True)
            self.assertEqual(self.project.settings["alerts"]["arbitration"], False)
            self.assertEqual(self.project.settings["alerts"]["instruction"], True)
            self.assertEqual(self.project.settings["alerts"]["control"], False)
            self.assertEqual(self.project.settings["alerts"]["edition"], True)
            self.assertEqual(self.project.settings["alerts"]["preservation"], False)
            self.assertEqual(self.project.settings["alerts"]["transfer"], True)

            # Verify exclusion_reasons are preserved
            expected_exclusions = [str(reason) for reason in DEFAULT_EXCLUSION_REASONS]
            self.assertEqual(self.project.settings["exclusion_reasons"], expected_exclusions)
        else:
            # Verify settings were not changed
            for alert_type in AlertType.values:
                self.assertEqual(
                    self.project.settings["alerts"][alert_type],
                    False,
                    f"Alert type {alert_type} should remain False when update fails",
                )
