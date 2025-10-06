from django.core import mail
from django_tenants.urlresolvers import reverse

from epl.apps.project.models import ResourceStatus, Role, UserRole
from epl.apps.project.models.choices import AlertType
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class AnomalyNotificationTest(TestCase):
    def setUp(self):
        super().setUp()

        self.project = ProjectFactory()
        self.project.settings["alerts"] = {AlertType.ANOMALY.value: True}
        self.project.save()

        self.library_1 = LibraryFactory()
        self.library_2 = LibraryFactory()

        self.resource = ResourceFactory(project=self.project)
        self.resource.status = ResourceStatus.INSTRUCTION_BOUND
        self.resource.save()

        # Create collections (non-excluded: position != 0)
        self.collection_1 = CollectionFactory(
            resource=self.resource,
            library=self.library_1,
            project=self.project,
            position=1,
        )
        self.collection_2 = CollectionFactory(
            resource=self.resource,
            library=self.library_2,
            project=self.project,
            position=2,
        )

        self.controller = UserWithRoleFactory(role=Role.CONTROLLER, project=self.project)
        self.instructor_1 = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library_1)
        self.instructor_2 = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library_2)
        self.project_admin = UserWithRoleFactory(role=Role.PROJECT_ADMIN, project=self.project)

    def test_controller_reports_anomaly_sends_notifications(self):
        mail.outbox = []

        # Controller reports anomaly
        response = self.patch(
            reverse("resource-report-anomalies", kwargs={"pk": self.resource.id}),
            content_type="application/json",
            user=self.controller,
        )
        self.assertEqual(response.status_code, 200)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.ANOMALY_BOUND)

        self.assertEqual(len(mail.outbox), 4)  # 2 instructors + 1 admin + 1 copy to controller

        recipients = [email.to[0] for email in mail.outbox]
        expected_recipients = {
            self.instructor_1.email,
            self.instructor_2.email,
            self.project_admin.email,
            self.controller.email,  # copy to sender # todo add copy as cc field in email
        }
        self.assertEqual(set(recipients), expected_recipients)

        # Check email content
        anomaly_emails = [email for email in mail.outbox if "anomaly" in str(email.subject).lower()]
        self.assertEqual(len(anomaly_emails), 4)

        # Check email subject
        for email in anomaly_emails:
            self.assertIn(self.project.name, str(email.subject))
            self.assertIn(self.resource.code, str(email.subject))
            self.assertIn("anomaly", str(email.subject).lower())

    def test_instructor_reports_anomaly_sends_notifications(self):
        mail.outbox = []

        # Instructor reports anomaly
        response = self.patch(
            reverse("resource-report-anomalies", kwargs={"pk": self.resource.id}),
            content_type="application/json",
            user=self.instructor_1,
        )
        self.assertEqual(response.status_code, 200)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.ANOMALY_BOUND)

        # Check emails sent
        recipients = [email.to[0] for email in mail.outbox]

        # Should notify: other instructors (not reporting one), project admin, other controllers, copy to instructor
        expected_recipients = {
            self.instructor_2.email,
            self.project_admin.email,
            self.instructor_1.email,
        }

        # Check if there are other controllers to notify
        other_controllers = UserRole.objects.filter(project=self.project, role=Role.CONTROLLER).exclude(
            user=self.instructor_1
        )

        for controller_role in other_controllers:
            expected_recipients.add(controller_role.user.email)

        self.assertEqual(set(recipients), expected_recipients)

    def test_excluded_collection_instructor_not_notified(self):
        """Test that instructors of excluded collections don't receive notifications"""
        # Exclude collection 2 by setting position = 0
        self.collection_2.position = 0
        self.collection_2.exclusion_reason = "Other"
        self.collection_2.save()

        self.assertTrue(self.collection_2.is_excluded)

        mail.outbox = []

        # Controller reports anomaly
        response = self.patch(
            reverse("resource-report-anomalies", kwargs={"pk": self.resource.id}),
            content_type="application/json",
            user=self.controller,
        )

        self.assertEqual(response.status_code, 200)

        recipients = [email.to[0] for email in mail.outbox]

        # Only instructor 1 should receive notification (not instructor 2)
        self.assertIn(self.instructor_1.email, recipients)
        self.assertNotIn(self.instructor_2.email, recipients)

        # Admin and controller should still receive notifications
        self.assertIn(self.project_admin.email, recipients)
        self.assertIn(self.controller.email, recipients)

    def test_no_anomaly_alerts_setting_no_notification(self):
        self.project.settings["alerts"] = {AlertType.ANOMALY.value: False}
        self.project.save()

        mail.outbox = []

        # Controller reports anomaly
        response = self.patch(
            reverse("resource-report-anomalies", kwargs={"pk": self.resource.id}),
            content_type="application/json",
            user=self.controller,
        )
        self.assertEqual(response.status_code, 200)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.ANOMALY_BOUND)

        self.assertEqual(len(mail.outbox), 0)

    def test_user_has_anomaly_alerts_disabled_not_notified(self):
        self.instructor_1.settings["alerts"] = {str(self.project.id): {AlertType.ANOMALY.value: False}}
        self.instructor_1.save()
        self.instructor_1.refresh_from_db()

        mail.outbox = []

        # Controller reports anomaly
        response = self.patch(
            reverse("resource-report-anomalies", kwargs={"pk": self.resource.id}),
            content_type="application/json",
            user=self.controller,
        )
        self.assertEqual(response.status_code, 200)

        recipients = [email.to[0] for email in mail.outbox]

        # instructor_1 should not receive notification (alerts disabled)
        self.assertNotIn(self.instructor_1.email, recipients)

        # Others should still receive notifications
        self.assertIn(self.instructor_2.email, recipients)
        self.assertIn(self.project_admin.email, recipients)
        self.assertIn(self.controller.email, recipients)  # copy to sender

    def test_email_content_and_format(self):
        mail.outbox = []

        # Controller reports anomaly
        response = self.patch(
            reverse("resource-report-anomalies", kwargs={"pk": self.resource.id}),
            content_type="application/json",
            user=self.controller,
        )
        self.assertEqual(response.status_code, 200)

        self.assertTrue(len(mail.outbox) > 0)

        # Check we have anomaly emails
        expected_string_in_subject = "anomaly"
        anomaly_emails = [
            email for email in mail.outbox if expected_string_in_subject.lower() in str(email.subject).lower()
        ]

        self.assertTrue(len(anomaly_emails) > 0)

        # Check email subjects
        expected_subject = f"eplouribousse | {self.tenant.name} | {self.project.name} | {self.resource.code} | anomaly"
        actual_subjects = {email.subject for email in anomaly_emails}

        # All anomaly emails should have the same subject
        self.assertEqual(len(actual_subjects), 1)

        actual_subject = list(actual_subjects)[0]
        self.assertEqual(actual_subject, expected_subject)

        # Check email body contains expected information
        for email in anomaly_emails:
            self.assertIn("One or more anomalies have been reported", email.body)
            self.assertIn(self.controller.username, email.body)
            self.assertIn(self.controller.email, email.body)
            self.assertIn(self.resource.title, email.body)
            self.assertIn(str(self.project.id), email.body)
