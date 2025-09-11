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
        Test les transitions de statut avec différents rôles utilisateur.
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

        # first email should be an invitation to epl
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.to, ["new_project_admin@test.com"])
        self.assertIn("invitation", sent_email.subject.lower())
        self.assertIn("invited", sent_email.body.lower())

        # second email should be a notification to review the project, for the already registered project admin
        sent_email = mail.outbox[1]
        self.assertEqual(sent_email.to, [self.project_admin.email])
        self.assertIn(self.project.name, sent_email.subject)
        self.assertIn("As an administrator, you must, in consultation with your co-administrators", sent_email.body)

    def test_send_invitation_to_review_project_after_new_project_admin_subscription(self):
        invited_user_email = "new_project_admin@test.com"
        invited_user_role = Role.PROJECT_ADMIN
        invited_user_password = "SecurePassword123!"  # noqa: S105

        invitation_payload = {
            "email": str(invited_user_email),
            "project_id": str(self.project.id),
            "library_id": None,
            "role": str(invited_user_role),
            "assigned_by_id": str(self.project_creator.id),
        }
        signer = TimestampSigner(salt=INVITE_TOKEN_SALT)
        token = signer.sign_object(invitation_payload)
        registration_url = reverse("create_account")

        registration_data = {
            "token": token,
            "password": invited_user_password,
            "confirm_password": invited_user_password,
        }

        response = self.client.post(registration_url, registration_data, format="json")
        self.project.refresh_from_db()
        self.response_created(response)

        try:
            new_user = User.objects.get(email=invited_user_email)
        except User.DoesNotExist:
            self.fail("User was not created in the database.")

        self.assertTrue(UserRole.objects.filter(user=new_user, project=self.project, role=Role.PROJECT_ADMIN).exists())

        self.assertEqual(len(mail.outbox), 2)
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.to, [new_user.email])
        self.assertIn("Creation of the Test Project project", sent_email.subject)
        self.assertIn(self.project.name, sent_email.body)

        self.assertEqual(len(self.project.invitations), 0)


class TestUpdateProjectStatusToLaunchTest(TestCase):
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
            "role": Role.PROJECT_MANAGER,
            "assigned_by_id": str(self.project_creator.id),
        }
        signer = TimestampSigner(salt=INVITE_TOKEN_SALT)
        token = signer.sign_object(invitation_payload)

        registration_url = reverse("create_account")
        registration_data = {
            "token": token,
            "password": self.invited_user_password,
            "confirm_password": self.invited_user_password,
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

        # An invitation to launch the project has been sent
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.to, [self.invited_user_email])
        self.assertIn(str(_("is now ready for launch")), sent_email.body)

    def test_manager_does_not_receive_notification_if_project_is_launched(self):
        """
        Checks that a project manager does not receive an invitation to launch the project,
        when subscribing after the project is launched.
        """
        project = ProjectFactory(
            status=ProjectStatus.LAUNCHED,
            invitations=[{"email": self.invited_user_email, "role": Role.PROJECT_MANAGER}],
        )

        self._register_invited_user(project)

        # check that the user has been created, but no invitation to launch the project has been sent
        user = User.objects.get(email=self.invited_user_email)
        user_role = UserRole.objects.get(user=user, project=project)
        self.assertEqual(user.username, self.invited_user_email)
        self.assertEqual(user_role.role, Role.PROJECT_MANAGER)
        self.assertEqual(len(mail.outbox), 0)
