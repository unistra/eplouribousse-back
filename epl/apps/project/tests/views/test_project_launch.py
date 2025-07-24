from django.core import mail
from django.utils import timezone
from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context

from epl.apps.project.models import ProjectStatus, Role
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import UserFactory
from epl.tests import TestCase


class ProjectLaunchTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.project_creator = UserFactory()
            self.project_admin = UserFactory()
            self.instructor = UserFactory()

            self.project = ProjectFactory(
                name="Test Project",
                description="This is a test project.",
                status=ProjectStatus.READY,
            )

            self.project.user_roles.create(user=self.project_creator, role=Role.PROJECT_CREATOR)
            self.project.user_roles.create(user=self.project_admin, role=Role.PROJECT_ADMIN)
            self.project.user_roles.create(user=self.instructor, role=Role.INSTRUCTOR)

    def test_set_status_to_launched_successfully_without_date(self):
        url = reverse("project-launch", kwargs={"pk": self.project.id})
        data = {"status": ProjectStatus.LAUNCHED}

        response = self.patch(url, data=data, content_type="application/json", user=self.project_creator)

        self.response_ok(response)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, ProjectStatus.LAUNCHED)
        self.assertLessEqual(self.project.active_after, timezone.now())

    def test_set_status_to_launched_successfully_with_date(self):
        url = reverse("project-launch", kwargs={"pk": self.project.id})
        future_date = (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        data = {
            "status": ProjectStatus.LAUNCHED,
            "active_after": future_date,
        }

        response = self.patch(url, data=data, content_type="application/json", user=self.project_creator)

        self.response_ok(response)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, ProjectStatus.LAUNCHED)
        self.assertEqual(timezone.localtime(self.project.active_after).strftime("%Y-%m-%dT%H:%M"), future_date)

    def test_launch_project_sends_notifications(self):
        url = reverse("project-launch", kwargs={"pk": self.project.id})
        data = {"status": ProjectStatus.LAUNCHED}

        self.patch(url, data=data, content_type="application/json", user=self.project_creator)

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]

        self.assertCountEqual(
            sent_email.to, [self.project_creator.email, self.project_admin.email, self.instructor.email]
        )

        self.assertIn(self.project.name, sent_email.subject)
        self.assertIn("launching project", sent_email.subject)

        self.assertIn(self.project.name, sent_email.body)
        self.assertIn("now", sent_email.body)  # is_starting_now=True par défaut

    def test_launch_project_with_future_date(self):
        future_date = timezone.now() + timezone.timedelta(days=7)
        self.project.active_after = future_date
        self.project.save()

        url = reverse("project-launch", kwargs={"pk": self.project.id})
        data = {"status": ProjectStatus.LAUNCHED, "active_after": future_date}

        response = self.patch(url, data=data, content_type="application/json", user=self.project_creator)

        self.response_ok(response)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, ProjectStatus.LAUNCHED)

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]

        formatted_date = future_date.strftime("%Y-%m-%d")
        self.assertIn(formatted_date, sent_email.body)
        self.assertNotIn("now", sent_email.body)
