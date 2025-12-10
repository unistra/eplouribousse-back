from django.core import mail
from django.utils.translation import gettext as _
from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context

from epl.apps.project.models import ResourceStatus, Role, UserRole
from epl.apps.project.models.choices import AlertType
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class ResultantReportAvailableNotificationTest(TestCase):
    """Test resultant report available notification"""

    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.project = ProjectFactory()
            self.project.settings["alerts"][AlertType.EDITION.value] = True
            self.project.save()

            self.library = LibraryFactory(project=self.project)
            self.resource = ResourceFactory(
                project=self.project,
                status=ResourceStatus.CONTROL_UNBOUND,
            )

            self.collection = CollectionFactory(
                library=self.library,
                position=1,
                project=self.project,
                resource=self.resource,
            )

            self.instructor = UserWithRoleFactory(
                project=self.project,
                role=Role.INSTRUCTOR,
                library=self.library,
            )

            self.controller = UserWithRoleFactory(
                project=self.project,
                role=Role.CONTROLLER,
            )

    def test_resultant_report_available_sends_notification(self):
        """Test that notification is sent to instructors when controller validates unbound control"""
        url = reverse("resource-validate-control", kwargs={"pk": self.resource.id})
        data = {"validation": True}
        response = self.post(url, data, content_type="application/json", user=self.controller)

        self.assertEqual(response.status_code, 200)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.EDITION)

        # Check email was sent
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]

        # Check subject
        expected_subject = f"eplouribousse | {self.tenant.name} | {self.project.name} | {self.library.code} | {self.resource.code} | {_('resultant')}"
        self.assertEqual(email.subject, expected_subject)

        # Check recipient
        self.assertIn(self.instructor.email, email.to)

        # Check body
        self.assertIn(self.resource.title, email.body)
        self.assertIn(f"/projects/{self.project.id}", email.body)

    def test_resultant_report_available_excludes_excluded_collections(self):
        """Test that instructors with excluded collections don't receive notification"""
        self.collection.position = 0
        self.collection.save()

        url = reverse("resource-validate-control", kwargs={"pk": self.resource.id})
        data = {"validation": True}
        response = self.post(url, data, content_type="application/json", user=self.controller)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_resultant_report_available_respects_user_settings(self):
        """Test that notification respects user alert settings"""
        self.instructor.settings.setdefault("alerts", {}).setdefault(str(self.project.id), {})[
            AlertType.EDITION.value
        ] = False
        self.instructor.save()
        self.instructor.refresh_from_db()

        url = reverse("resource-validate-control", kwargs={"pk": self.resource.id})
        data = {"validation": True}
        response = self.post(url, data, content_type="application/json", user=self.controller)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_resultant_report_available_respects_project_settings(self):
        """Test that notification respects project alert settings"""
        self.project.settings["alerts"][AlertType.EDITION.value] = False
        self.project.save()

        url = reverse("resource-validate-control", kwargs={"pk": self.resource.id})
        data = {"validation": True}
        response = self.post(url, data, content_type="application/json", user=self.controller)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_resultant_report_available_multiple_instructors(self):
        """Test that notification is sent to all concerned instructors"""
        with tenant_context(self.tenant):
            library2 = LibraryFactory(project=self.project)
            instructor2 = UserWithRoleFactory(
                project=self.project,
                role=Role.INSTRUCTOR,
                library=library2,
            )
            _collection2 = CollectionFactory(
                library=library2,
                position=2,
                project=self.project,
                resource=self.resource,
            )

        url = reverse("resource-validate-control", kwargs={"pk": self.resource.id})
        data = {"validation": True}
        response = self.post(url, data, content_type="application/json", user=self.controller)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)

        expected_recipients = {self.instructor.email, instructor2.email}
        actual_recipients = {email.to[0] for email in mail.outbox}
        self.assertEqual(actual_recipients, expected_recipients)

    def test_resultant_report_available_no_instructors(self):
        """Test that no notification is sent when there are no instructors"""
        UserRole.objects.filter(user=self.instructor).delete()

        url = reverse("resource-validate-control", kwargs={"pk": self.resource.id})
        data = {"validation": True}
        response = self.post(url, data, content_type="application/json", user=self.controller)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_resultant_report_available_not_called_on_bound_validation(self):
        """Test that notification is not sent when validating CONTROL_BOUND"""

        self.resource.status = ResourceStatus.CONTROL_BOUND
        self.resource.instruction_turns = {
            "bound_copies": {"turns": [{"library": str(self.library.id), "collection": str(self.collection.id)}]},
            "unbound_copies": {"turns": [{"library": str(self.library.id), "collection": str(self.collection.id)}]},
        }
        self.resource.save()

        url = reverse("resource-validate-control", kwargs={"pk": self.resource.id})
        data = {"validation": True}
        response = self.post(url, data, content_type="application/json", user=self.controller)

        self.assertEqual(response.status_code, 200)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.INSTRUCTION_UNBOUND)

        resultant_emails = [email for email in mail.outbox if _("resultant") in email.subject]
        self.assertEqual(len(resultant_emails), 0)
