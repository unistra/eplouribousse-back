from django.core import mail
from django.core.signing import TimestampSigner
from django.utils.translation import gettext_lazy as _
from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context
from parameterized import parameterized

from epl.apps.project.models import Project, ProjectStatus, Role, UserRole
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import ProjectCreatorFactory, UserFactory, UserWithRoleFactory
from epl.apps.user.models import User
from epl.apps.user.views import INVITE_TOKEN_SALT
from epl.tests import TestCase


class ProjectStatusListTest(TestCase):
    def test_list_available_statuses(self):
        response = self.get(reverse("project-list-statuses"))
        self.response_ok(response)
        self.assertListEqual(
            [_s["status"] for _s in response.data],
            [_s[0] for _s in ProjectStatus.choices],
        )


class UpdateProjectStatusTest(TestCase):
    STATUS_TRANSITIONS = {
        (ProjectStatus.DRAFT, ProjectStatus.REVIEW): Role.PROJECT_CREATOR,
        (ProjectStatus.REVIEW, ProjectStatus.READY): Role.PROJECT_ADMIN,
        (ProjectStatus.READY, ProjectStatus.LAUNCHED): Role.PROJECT_MANAGER,
    }

    @parameterized.expand(
        [
            # Generates all possible combinations of status transitions and roles,
            # then checks if the tested role is allowed to perform the transition (should_succeed)
            # and the expected response code (200 if allowed, 403 otherwise).
            (target, initial, role, role == allowed_role, 200 if role == allowed_role else 403)
            for (initial, target), allowed_role in STATUS_TRANSITIONS.items()
            for role in [
                Role.PROJECT_CREATOR,
                Role.INSTRUCTOR,
                Role.PROJECT_ADMIN,
                Role.PROJECT_MANAGER,
                Role.CONTROLLER,
                Role.GUEST,
                None,
            ]
        ]
    )
    def test_update_status(self, target_status, initial_status, role, should_succeed, expected_status_code):
        """
        Teste les transitions de statut avec différents rôles utilisateur.
        """
        project = ProjectFactory(status=initial_status)
        library = LibraryFactory()
        user = UserWithRoleFactory(role=role, project=project, library=library)

        response = self.patch(
            reverse("project-update-status", kwargs={"pk": project.id}),
            data={"status": target_status},
            content_type="application/json",
            user=user,
        )

        self.assertEqual(response.status_code, expected_status_code)
        project.refresh_from_db()
        self.assertEqual(project.status, target_status if should_succeed else initial_status)

    def test_update_project_status_invalid(self):
        user = ProjectCreatorFactory(first_name="Annabelle")
        project: Project = ProjectFactory(status=ProjectStatus.DRAFT)
        response = self.patch(
            reverse("project-update-status", kwargs={"pk": project.id}),
            data={"status": 300},
            content_type="application/json",
            user=user,
        )
        self.response_bad_request(response)


class TestUpdateProjectStatusToReviewTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.project_creator = UserFactory()
            self.project_admin = UserFactory()

            self.project = ProjectFactory(
                name="Test Project",
                description="This is a test project.",
                status=ProjectStatus.DRAFT,
                invitations=[{"email": "new_project_admin@test.com", "role": Role.PROJECT_ADMIN}],
            )

            self.project.user_roles.create(user=self.project_creator, role=Role.PROJECT_CREATOR)
            self.project.user_roles.create(user=self.project_admin, role=Role.PROJECT_ADMIN)

    def test_set_status_to_review_success(self):
        url = reverse("project-update-status", kwargs={"pk": self.project.id})
        data = {"status": ProjectStatus.REVIEW}

        response = self.patch(url, data=data, content_type="application/json", user=self.project_creator)

        self.response_ok(response)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, ProjectStatus.REVIEW)

    def test_set_status_to_review_sends_invitations(self):
        url = reverse("project-update-status", kwargs={"pk": self.project.id})
        data = {"status": ProjectStatus.REVIEW}

        response = self.patch(url, data=data, content_type="application/json", user=self.project_creator)

        self.response_ok(response)
        self.project.refresh_from_db()
        self.assertEqual(len(mail.outbox), 2)

        # L'ordre des e-mails n'est pas garanti, nous vérifions donc la présence des deux.
        recipient_emails = {email.to[0] for email in mail.outbox}
        self.assertSetEqual(recipient_emails, {"new_project_admin@test.com", self.project_admin.email})

        invitation_email = next(email for email in mail.outbox if email.to[0] == "new_project_admin@test.com")
        notification_email = next(email for email in mail.outbox if email.to[0] == self.project_admin.email)

        self.assertIn(_("creating").lower(), invitation_email.subject.lower())
        self.assertIn(_("invited").lower(), invitation_email.body.lower())

        self.assertIn(self.project.name, notification_email.subject)
        self.assertIn(
            "As an administrator, you must, in consultation with your co-administrators", notification_email.body
        )


class TestUpdateProjectStatusToReadyTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.project_creator = UserFactory()
            self.project_admin = UserFactory()
            self.project_manager = UserFactory()

            self.project = ProjectFactory(
                name="Test Project",
                description="This is a test project.",
                status=ProjectStatus.REVIEW,
                invitations=[{"email": "new_project_manager@test.com", "role": Role.PROJECT_MANAGER}],
            )

            self.project.user_roles.create(user=self.project_creator, role=Role.PROJECT_CREATOR)
            self.project.user_roles.create(user=self.project_admin, role=Role.PROJECT_ADMIN)
            self.project.user_roles.create(user=self.project_manager, role=Role.PROJECT_MANAGER)

    def test_set_status_to_ready_invites_project_managers_to_launch_project(self):
        """
        Check that project managers are notified when a project is set to ready.
        """
        url = reverse("project-update-status", kwargs={"pk": self.project.id})
        data = {"status": ProjectStatus.READY}
        response = self.patch(url, data=data, content_type="application/json", user=self.project_admin)

        self.response_ok(response)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, ProjectStatus.READY)

        self.assertEqual(len(mail.outbox), 1)

        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.to, [self.project_manager.email])

        self.assertIn(self.project.name, sent_email.subject)
        self.assertIn(str(_("As a pilot, you can now launch or schedule")), sent_email.body)


class TestSubscriptionNotificationForProjectManagers(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.project_creator = UserFactory()
            self.invited_user_email = "new_manager@test.com"
            self.invited_user_password = "SecurePassword123!"  # noqa: S105

    def _register_invited_user(self, project: Project):
        """Simulates a user registering after receiving an invitation."""
        invitation_payload = {
            "email": self.invited_user_email,
            "project_id": str(project.id),
            "invitations": [
                {
                    "role": Role.PROJECT_MANAGER,
                    "library_id": None,
                }
            ],
            "assigned_by_id": str(self.project_creator.id),
        }
        signer = TimestampSigner(salt=INVITE_TOKEN_SALT)
        token = signer.sign_object(invitation_payload)

        registration_url = reverse("create_account")
        registration_data = {
            "token": token,
            "password": self.invited_user_password,
            "confirm_password": self.invited_user_password,
            "first_name": "Eplou",
            "last_name": "Ribousse",
        }

        mail.outbox = []
        response = self.client.post(registration_url, registration_data, format="json")
        self.response_created(response)

    def test_manager_receives_notification_if_project_is_ready(self):
        """
        Checks that a project manager receives a notification, when subscribing when the project is ready.
        """
        project = ProjectFactory(
            status=ProjectStatus.READY, invitations=[{"email": self.invited_user_email, "role": Role.PROJECT_MANAGER}]
        )
        self._register_invited_user(project)

        # 2 emails are sent: account confirmation and invitation to launch the project.
        self.assertEqual(len(mail.outbox), 2)
        subjects = [email.subject for email in mail.outbox]
        bodies = [email.body for email in mail.outbox]
        account_creation_subject_part = str(_("your account creation"))
        project_ready_body_part = str(_("is now ready for launch"))
        self.assertTrue(any(account_creation_subject_part in s for s in subjects))
        self.assertTrue(any(project_ready_body_part in b for b in bodies))


class TestSubscriptionNotificationForProjectAdmins(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.project_creator = UserFactory()
            self.invited_user_email = "new_admin@test.com"
            self.invited_user_password = "SecurePassword123!"  # noqa: S105

    def _register_invited_user(self, project: Project):
        """Simulates an admin registering after receiving an invitation."""
        invitation_payload = {
            "email": self.invited_user_email,
            "project_id": str(project.id),
            "invitations": [
                {
                    "role": Role.PROJECT_ADMIN,
                    "library_id": None,
                }
            ],
            "assigned_by_id": str(self.project_creator.id),
        }
        signer = TimestampSigner(salt=INVITE_TOKEN_SALT)
        token = signer.sign_object(invitation_payload)

        registration_url = reverse("create_account")
        registration_data = {
            "token": token,
            "password": self.invited_user_password,
            "confirm_password": self.invited_user_password,
            "first_name": "Eplou",
            "last_name": "Ribousse",
        }

        mail.outbox = []
        response = self.client.post(registration_url, registration_data, format="json")
        self.response_created(response)

    def test_admin_receives_notification_if_project_is_in_review(self):
        """
        Checks that an admin receives a notification to review the project
        when subscribing if the project is in REVIEW status.
        """
        project = ProjectFactory(
            status=ProjectStatus.REVIEW, invitations=[{"email": self.invited_user_email, "role": Role.PROJECT_ADMIN}]
        )
        self._register_invited_user(project)

        # 2 emails are sent: account confirmation and invitation to review the project.
        self.assertEqual(len(mail.outbox), 2)
        bodies = [email.body for email in mail.outbox]
        project_review_body_part = str(_("As an administrator, you must, in consultation with your co-administrators"))
        self.assertTrue(any(project_review_body_part in b for b in bodies))

    def test_admin_not_invited_to_review_if_project_status_is_ready(self):
        """
        Checks that an admin is NOT invited to review the project if it is
        already in READY status during their subscription.
        """
        project = ProjectFactory(
            status=ProjectStatus.READY,
            invitations=[{"email": self.invited_user_email, "role": Role.PROJECT_ADMIN}],
        )

        self._register_invited_user(project)
        user = User.objects.get(email=self.invited_user_email)

        self.assertTrue(UserRole.objects.filter(user=user, project=project, role=Role.PROJECT_ADMIN).exists())
        # Check that the only email sent is the confirmation of registration.
        self.assertEqual(len(mail.outbox), 1)
        expected_string_in_subject = str(_("your account creation"))
        self.assertIn(expected_string_in_subject, mail.outbox[0].subject)
