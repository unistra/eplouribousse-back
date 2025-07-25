from django.core import mail
from django.utils import timezone
from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context
from parameterized import parameterized

from epl.apps.project.models import ProjectStatus, Role
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class ProjectLaunchTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.library = LibraryFactory()
            self.project = ProjectFactory(
                name="Test Project",
                description="This is a test project.",
                status=ProjectStatus.READY,
            )

            self.url = reverse("project-launch", kwargs={"pk": self.project.id})
            self.project_manager = UserWithRoleFactory(role=Role.PROJECT_MANAGER, project=self.project)
            self.future_date = (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
            self.future_date_data = {"active_after": self.future_date}

    @parameterized.expand(
        [
            (Role.PROJECT_CREATOR, True, 200),
            (Role.PROJECT_ADMIN, False, 403),
            (Role.PROJECT_MANAGER, True, 200),
            (Role.INSTRUCTOR, False, 403),
            (Role.CONTROLLER, False, 403),
            (Role.GUEST, False, 403),
            (None, False, 403),
        ]
    )
    def test_project_launch_permissions(self, role, should_succeed, expected_status):
        user = UserWithRoleFactory(role=role, project=self.project, library=self.library)

        response = self.patch(self.url, content_type="application/json", user=user)
        self.project.refresh_from_db()

        self.assertEqual(response.status_code, expected_status)
        if should_succeed:
            self.assertEqual(self.project.status, ProjectStatus.LAUNCHED)
            self.assertLessEqual(self.project.active_after, timezone.now())
        else:
            self.assertEqual(self.project.status, ProjectStatus.READY)

    def test_project_launch_with_date(self):
        response = self.patch(
            self.url, data=self.future_date_data, content_type="application/json", user=self.project_manager
        )
        self.project.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.project.status, ProjectStatus.LAUNCHED)
        self.assertEqual(timezone.localtime(self.project.active_after).strftime("%Y-%m-%dT%H:%M"), self.future_date)

    def _create_users(self):
        return {
            "instructor": UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library),
            "admin": UserWithRoleFactory(role=Role.PROJECT_ADMIN, project=self.project),
            "controller": UserWithRoleFactory(role=Role.CONTROLLER, project=self.project),
            "manager": self.project_manager,
        }

    def _assert_email_sent(self, users, subject_contains, body_contains):
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertCountEqual(sent_email.to, [u.email for u in users.values()])
        self.assertIn(self.project.name, sent_email.subject)
        for text in subject_contains:
            self.assertIn(text, sent_email.subject)
        for text in body_contains:
            self.assertIn(text, sent_email.body)

    def test_launch_project_sends_notifications(self):
        users = self._create_users()
        response = self.patch(self.url, content_type="application/json", user=self.project_manager)
        self.assertEqual(response.status_code, 200)
        self._assert_email_sent(
            users,
            subject_contains=["launching project"],
            body_contains=[self.project.name, "now"],
        )

    def test_launch_project_in_future_sends_notifications(self):
        users = self._create_users()
        response = self.patch(
            self.url,
            data=self.future_date_data,
            content_type="application/json",
            user=self.project_manager,
        )
        self.project.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            timezone.localtime(self.project.active_after).strftime("%Y-%m-%dT%H:%M"),
            self.future_date,
        )
        self._assert_email_sent(
            users,
            subject_contains=["launching project"],
            body_contains=[timezone.localtime(self.project.active_after).strftime("%Y-%m-%d")],
        )
