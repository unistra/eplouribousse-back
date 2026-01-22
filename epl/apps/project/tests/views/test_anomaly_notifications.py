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
        self.project.settings["alerts"] = {AlertType.INSTRUCTION.value: True}
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

        # Should send 1 email with multiple TO and CC recipients
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]

        # Check TO recipients (instructors + admin, excluding reporter)
        expected_to = {
            self.instructor_1.email,
            self.instructor_2.email,
            self.project_admin.email,
        }
        actual_to = set(email.to)
        self.assertEqual(actual_to, expected_to)

        # Check CC recipients (reporter)
        expected_cc = {self.controller.email}
        actual_cc = set(email.cc)
        self.assertEqual(actual_cc, expected_cc)

        # Check email subject
        self.assertIn(self.project.name, email.subject)
        self.assertIn(self.resource.code, email.subject)
        self.assertIn("anomaly", email.subject.lower())

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

        # Should send 1 email
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]

        # Check TO recipients (other instructor + admin + controllers, excluding reporter)
        expected_to = {self.instructor_2.email, self.project_admin.email}

        # Add other controllers to expected_to
        other_controllers = UserRole.objects.filter(project=self.project, role=Role.CONTROLLER).exclude(
            user=self.instructor_1
        )
        for controller_role in other_controllers:
            expected_to.add(controller_role.user.email)

        actual_to = set(email.to)
        self.assertEqual(actual_to, expected_to)

        # Check CC recipients (reporter instructor)
        expected_cc = {self.instructor_1.email}
        actual_cc = set(email.cc)
        self.assertEqual(actual_cc, expected_cc)

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

        # Should send 1 email
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]

        # Check TO recipients (instructor_1 + admin, excluding instructor_2 and reporter)
        expected_to = {self.instructor_1.email, self.project_admin.email}
        actual_to = set(email.to)
        self.assertEqual(actual_to, expected_to)

        # Check CC recipients (reporter)
        expected_cc = {self.controller.email}
        actual_cc = set(email.cc)
        self.assertEqual(actual_cc, expected_cc)

        # Verify instructor_2 is NOT in TO or CC (excluded collection)
        self.assertNotIn(self.instructor_2.email, email.to)
        self.assertNotIn(self.instructor_2.email, email.cc)

    def test_no_anomaly_alerts_setting_no_notification(self):
        self.project.settings["alerts"] = {AlertType.INSTRUCTION.value: False}
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
        self.instructor_1.settings["alerts"] = {str(self.project.id): {AlertType.INSTRUCTION.value: False}}
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

        # Should send 1 email
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]

        # Check TO recipients (instructor_2 + admin, excluding instructor_1 and reporter)
        expected_to = {self.instructor_2.email, self.project_admin.email}
        actual_to = set(email.to)
        self.assertEqual(actual_to, expected_to)

        # Check CC recipients (reporter)
        expected_cc = {self.controller.email}
        actual_cc = set(email.cc)
        self.assertEqual(actual_cc, expected_cc)

        # Verify instructor_1 is NOT in TO or CC (alerts disabled)
        self.assertNotIn(self.instructor_1.email, email.to)
        self.assertNotIn(self.instructor_1.email, email.cc)

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


class AnomalyResolvedNotificationTest(TestCase):
    def setUp(self):
        super().setUp()

        # Create project with INSTRUCTION alerts enabled
        self.project = ProjectFactory()
        self.project.settings["alerts"] = {AlertType.INSTRUCTION.value: True}
        self.project.save()

        # Create libraries
        self.library_1 = LibraryFactory()
        self.library_2 = LibraryFactory()
        self.library_3 = LibraryFactory()

        # Create resource in ANOMALY status
        self.resource = ResourceFactory(project=self.project)
        self.resource.status = ResourceStatus.ANOMALY_BOUND
        self.resource.save()

        # Create collections
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
        self.collection_3 = CollectionFactory(
            resource=self.resource,
            library=self.library_3,
            project=self.project,
            position=3,
        )

        # Set up instruction turns - library_1 has the next turn
        self.resource.instruction_turns = {
            "bound_copies": {
                "turns": [
                    {"library": str(self.library_1.id), "collection": str(self.collection_1.id)},
                    {"library": str(self.library_2.id), "collection": str(self.collection_2.id)},
                    {"library": str(self.library_3.id), "collection": str(self.collection_3.id)},
                ]
            },
            "unbound_copies": {"turns": []},
        }
        self.resource.save()

        # Create users
        self.project_admin = UserWithRoleFactory(role=Role.PROJECT_ADMIN, project=self.project)
        self.instructor_1 = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library_1)
        self.instructor_2 = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library_2)
        self.instructor_3 = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library_3)

    def test_admin_resolves_anomaly_sends_notifications_with_correct_recipients(self):
        """Test that when an admin resolves an anomaly, correct TO and CC recipients are used"""
        mail.outbox = []

        # Admin resolves anomaly (reset instruction)
        response = self.patch(
            reverse("resource-reset-instruction", kwargs={"pk": self.resource.id}),
            content_type="application/json",
            user=self.project_admin,
        )
        self.assertEqual(response.status_code, 200)

        # Verify resource status changed
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.INSTRUCTION_BOUND)

        # Check that emails were sent
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]

        # Check TO recipients (instructor with turn + project admin)
        expected_to = {self.instructor_1.email, self.project_admin.email}
        actual_to = set(email.to)
        self.assertEqual(actual_to, expected_to)

        # Check CC recipients (other instructors)
        expected_cc = {self.instructor_2.email, self.instructor_3.email}
        actual_cc = set(email.cc)
        self.assertEqual(actual_cc, expected_cc)

    def test_email_subject_format(self):
        """Test that email subject has correct format"""
        mail.outbox = []

        response = self.patch(
            reverse("resource-reset-instruction", kwargs={"pk": self.resource.id}),
            content_type="application/json",
            user=self.project_admin,
        )
        self.assertEqual(response.status_code, 200)

        email = mail.outbox[0]
        expected_subject = (
            f"eplouribousse | {self.tenant.name} | {self.project.name} | {self.resource.code} | anomaly resolved"
        )
        self.assertEqual(email.subject, expected_subject)

    def test_email_body_content(self):
        """Test that email body contains expected information"""
        mail.outbox = []

        response = self.patch(
            reverse("resource-reset-instruction", kwargs={"pk": self.resource.id}),
            content_type="application/json",
            user=self.project_admin,
        )
        self.assertEqual(response.status_code, 200)

        email = mail.outbox[0]

        # Check that body contains expected elements
        self.assertIn(str(self.library_1.code), email.body)  # Library with the turn
        self.assertIn(self.project_admin.username, email.body)  # Admin who resolved
        self.assertIn(self.project_admin.email, email.body)  # Admin email
        self.assertIn(str(self.project.id), email.body)  # Project URL

    def test_no_notifications_when_alerts_disabled(self):
        """Test that no notifications are sent when anomaly alerts are disabled"""
        # Disable anomaly alerts
        self.project.settings["alerts"] = {AlertType.INSTRUCTION.value: False}
        self.project.save()

        mail.outbox = []

        response = self.patch(
            reverse("resource-reset-instruction", kwargs={"pk": self.resource.id}),
            content_type="application/json",
            user=self.project_admin,
        )
        self.assertEqual(response.status_code, 200)

        # No emails should be sent
        self.assertEqual(len(mail.outbox), 0)

    def test_user_with_disabled_alerts_not_notified(self):
        """Test that users with disabled anomaly alerts don't receive notifications"""
        # Disable alerts for instructor_1 (who has the turn)
        self.instructor_1.settings["alerts"] = {str(self.project.id): {AlertType.INSTRUCTION.value: False}}
        self.instructor_1.save()

        mail.outbox = []

        response = self.patch(
            reverse("resource-reset-instruction", kwargs={"pk": self.resource.id}),
            content_type="application/json",
            user=self.project_admin,
        )
        self.assertEqual(response.status_code, 200)

        email = mail.outbox[0]

        # instructor_1 should not be in TO (alerts disabled)
        self.assertNotIn(self.instructor_1.email, email.to)

        # But project admin should still be in TO
        self.assertIn(self.project_admin.email, email.to)

        # Other instructors should still be in CC
        self.assertIn(self.instructor_2.email, email.cc)
        self.assertIn(self.instructor_3.email, email.cc)

    def test_excluded_collection_instructor_not_in_cc(self):
        """Test that instructors of excluded collections are not in CC"""
        # Exclude collection_3
        self.collection_3.position = 0
        self.collection_3.save()

        mail.outbox = []

        response = self.patch(
            reverse("resource-reset-instruction", kwargs={"pk": self.resource.id}),
            content_type="application/json",
            user=self.project_admin,
        )
        self.assertEqual(response.status_code, 200)

        email = mail.outbox[0]

        # instructor_3 should not be in CC (excluded collection)
        self.assertNotIn(self.instructor_3.email, email.cc)

        # instructor_2 should still be in CC
        self.assertIn(self.instructor_2.email, email.cc)

    def test_multiple_project_admins_all_notified(self):
        """Test that all project admins receive notifications in TO"""
        # Create additional project admin
        project_admin_2 = UserWithRoleFactory(role=Role.PROJECT_ADMIN, project=self.project)

        mail.outbox = []

        response = self.patch(
            reverse("resource-reset-instruction", kwargs={"pk": self.resource.id}),
            content_type="application/json",
            user=self.project_admin,
        )
        self.assertEqual(response.status_code, 200)

        email = mail.outbox[0]

        # Both admins should be in TO
        self.assertIn(self.project_admin.email, email.to)
        self.assertIn(project_admin_2.email, email.to)

    def test_unbound_resource_anomaly_resolved_complete_unbound_cycle_reset(self):
        """Test notification for ANOMALY_UNBOUND resource with complete unbound cycle reset"""

        self.resource.status = ResourceStatus.ANOMALY_UNBOUND

        self.resource.instruction_turns = {
            "bound_copies": {"turns": []},  # Bound phase was completed
            "unbound_copies": {
                "turns": [
                    {"library": str(self.library_1.id), "collection": str(self.collection_1.id)},
                    {"library": str(self.library_2.id), "collection": str(self.collection_2.id)},
                    {"library": str(self.library_3.id), "collection": str(self.collection_3.id)},
                ]
            },
        }
        self.resource.save()

        mail.outbox = []

        response = self.patch(
            reverse("resource-reset-instruction", kwargs={"pk": self.resource.id}),
            content_type="application/json",
            user=self.project_admin,
        )
        self.assertEqual(response.status_code, 200)

        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.INSTRUCTION_UNBOUND)

        expected_turns = [
            {"library": str(self.library_1.id), "collection": str(self.collection_1.id)},
            {"library": str(self.library_2.id), "collection": str(self.collection_2.id)},
            {"library": str(self.library_3.id), "collection": str(self.collection_3.id)},
        ]
        self.assertEqual(self.resource.instruction_turns["unbound_copies"]["turns"], expected_turns)

        email = mail.outbox[0]

        # library_1 should be in TO (has the first turn after reset)
        self.assertIn(self.instructor_1.email, email.to)

        # Project admin should also be in TO
        self.assertIn(self.project_admin.email, email.to)

        # library_2 and library_3 should be in CC (other instructors concerned)
        expected_cc = {self.instructor_2.email, self.instructor_3.email}
        self.assertEqual(set(email.cc), expected_cc)

        # Check email content contains library_1 code (the library with the turn)
        self.assertIn(str(self.library_1.code), email.body)

    # todo: à tester quand la fonctionalité d'attribution du tour suite à la correction d'une anomalie sera implémentée.
    # def test_unbound_resource_anomaly_resolved_admin_gives_turn_to_specific_instructor(self):
    #     """Test notification when admin resolves ANOMALY_UNBOUND and gives turn to specific instructor"""
    #
    #     self.resource.status = ResourceStatus.ANOMALY_UNBOUND
    #
    #     self.resource.instruction_turns = {
    #         "bound_copies": {"turns": []},
    #         "unbound_copies": {
    #             "turns": [
    #                 {"library": str(self.library_2.id), "collection": str(self.collection_2.id)},
    #                 {"library": str(self.library_3.id), "collection": str(self.collection_3.id)},
    #             ]
    #         },
    #     }
    #     self.resource.save()
    #
    #     mail.outbox = []
    #
    #     response = self.patch(
    #         reverse("resource-reset-instruction", kwargs={"pk": self.resource.id}),
    #         content_type="application/json",
    #         user=self.project_admin,
    #     )
    #     self.assertEqual(response.status_code, 200)
    #
    #     # Verify resource is now INSTRUCTION_UNBOUND
    #     self.resource.refresh_from_db()
    #     self.assertEqual(self.resource.status, ResourceStatus.INSTRUCTION_UNBOUND)
    #
    #     # After reset, the turns should be recreated in position order (1,2,3)
    #     # But the notification should be based on who gets the FIRST turn
    #     expected_turns_after_reset = [
    #         {"library": str(self.library_1.id), "collection": str(self.collection_1.id)},
    #         {"library": str(self.library_2.id), "collection": str(self.collection_2.id)},
    #         {"library": str(self.library_3.id), "collection": str(self.collection_3.id)},
    #     ]
    #     self.assertEqual(self.resource.instruction_turns["unbound_copies"]["turns"], expected_turns_after_reset)
    #
    #     email = mail.outbox[0]
    #
    #     # library_1 should be in TO (gets the first turn after reset, regardless of pre-reset order)
    #     self.assertIn(self.instructor_1.email, email.to)
    #
    #     # Project admin should also be in TO
    #     self.assertIn(self.project_admin.email, email.to)
    #
    #     # library_2 and library_3 should be in CC (other instructors concerned)
    #     expected_cc = {self.instructor_2.email, self.instructor_3.email}
    #     self.assertEqual(set(email.cc), expected_cc)
    #
    #     # Check email content contains library_1 code (the library that actually gets the turn)
    #     self.assertIn(str(self.library_1.code), email.body)
    #
    #     # Check that admin info is in email body
    #     self.assertIn(self.project_admin.username, email.body)
    #     self.assertIn(self.project_admin.email, email.body)

    def test_no_emails_sent_when_no_to_recipients(self):
        """Test that no email is sent when there are no TO recipients"""
        # Disable alerts for the project admin
        self.project_admin.settings["alerts"] = {str(self.project.id): {AlertType.INSTRUCTION.value: False}}
        self.project_admin.save()

        # Disable alerts for instructor with turn
        self.instructor_1.settings["alerts"] = {str(self.project.id): {AlertType.INSTRUCTION.value: False}}
        self.instructor_1.save()

        mail.outbox = []

        response = self.patch(
            reverse("resource-reset-instruction", kwargs={"pk": self.resource.id}),
            content_type="application/json",
            user=self.project_admin,
        )
        self.assertEqual(response.status_code, 200)

        # No emails should be sent (no TO recipients)
        self.assertEqual(len(mail.outbox), 0)

    def test_instructor_not_duplicated_in_to_and_cc(self):
        """Test that an instructor is not in both TO and CC lists"""
        # This test ensures the exclude logic works correctly
        mail.outbox = []

        response = self.patch(
            reverse("resource-reset-instruction", kwargs={"pk": self.resource.id}),
            content_type="application/json",
            user=self.project_admin,
        )
        self.assertEqual(response.status_code, 200)

        email = mail.outbox[0]

        # instructor_1 should only be in TO (has the turn)
        self.assertIn(self.instructor_1.email, email.to)
        self.assertNotIn(self.instructor_1.email, email.cc)

        # instructor_2 and instructor_3 should only be in CC
        self.assertNotIn(self.instructor_2.email, email.to)
        self.assertNotIn(self.instructor_3.email, email.to)
        self.assertIn(self.instructor_2.email, email.cc)
        self.assertIn(self.instructor_3.email, email.cc)
