from django.core import mail
from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context
from parameterized import parameterized

from epl.apps.project.models import ProjectStatus, Role, UserRole
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import UserFactory
from epl.apps.user.models import User
from epl.apps.user.views import _get_invite_signer
from epl.tests import TestCase


class TestInvitationAndRoleAssignmentForNonDraftProjects(TestCase):
    """
    Tests for invitation and role assignment functionality when project status > DRAFT
    """

    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            # Create base users and admin
            self.project_admin = UserFactory()
            self.library = LibraryFactory()

            # Clear mail outbox
            mail.outbox = []

    def _create_project_with_status_and_admin(self, status: ProjectStatus):
        """Helper to create a project with specific status and admin"""
        project = ProjectFactory(status=status)
        project.libraries.add(self.library)

        UserRole.objects.create(
            user=self.project_admin,
            project=project,
            role=Role.PROJECT_CREATOR,
            assigned_by=self.project_admin,
        )
        return project

    @parameterized.expand(
        [
            (ProjectStatus.REVIEW, "new_user_review@example.com", Role.PROJECT_ADMIN),
            (ProjectStatus.READY, "new_user_ready@example.com", Role.PROJECT_MANAGER),
            (ProjectStatus.LAUNCHED, "new_user_launched@example.com", Role.GUEST),
        ]
    )
    def test_invitation_sent_immediately_for_non_draft_projects(self, project_status, email, role):
        """
        Test that invitations are sent immediately for projects with status > DRAFT
        """
        project = self._create_project_with_status_and_admin(project_status)

        url = reverse("project-add-invitation", kwargs={"pk": project.pk})
        data = {
            "email": email,
            "role": role,
        }

        # Clear mail outbox
        mail.outbox = []

        response = self.post(url, data=data, user=self.project_admin)
        self.assertEqual(response.status_code, 201)

        # Verify email was sent immediately
        self.assertEqual(len(mail.outbox), 1)

        # Verify invitation is stored for account creation process
        project.refresh_from_db()
        self.assertTrue(any(inv.get("email") == email and inv.get("role") == role for inv in project.invitations))

    @parameterized.expand(
        [
            (ProjectStatus.REVIEW, Role.PROJECT_ADMIN),
            (ProjectStatus.READY, Role.PROJECT_MANAGER),
            (ProjectStatus.LAUNCHED, Role.GUEST),
        ]
    )
    def test_existing_user_role_assignment_for_non_draft_projects(self, project_status, role):
        """
        Test that existing users can be assigned roles when project status > DRAFT
        """
        project = self._create_project_with_status_and_admin(project_status)
        existing_user = UserFactory(email=f"existing_{project_status.name.lower()}@example.com")

        url = reverse("project-assign-roles", kwargs={"pk": project.pk})
        data = {
            "user_id": str(existing_user.id),
            "role": role,
        }

        # Clear mail outbox
        mail.outbox = []

        response = self.post(url, data=data, user=self.project_admin)
        self.assertEqual(response.status_code, 201)

        # Verify user role was created
        user_role = UserRole.objects.get(user=existing_user, project=project, role=role)
        self.assertEqual(user_role.assigned_by, self.project_admin)


class TestEmailNotificationsForRoleAssignment(TestCase):
    """
    Tests for email notifications sent when users are added to projects based on project status and role
    """

    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.project_admin = UserFactory()
            self.library = LibraryFactory()
            mail.outbox = []

    def _create_project_with_status_and_admin(self, status: ProjectStatus):
        """Helper to create a project with specific status and admin"""
        project = ProjectFactory(status=status)
        project.libraries.add(self.library)

        UserRole.objects.create(
            user=self.project_admin,
            project=project,
            role=Role.PROJECT_CREATOR,
            assigned_by=self.project_admin,
        )
        return project

    def test_project_admin_receives_review_email_when_added_to_review_project(self):
        """
        Test that PROJECT_ADMIN receives review email when added to project with REVIEW status
        """
        project = self._create_project_with_status_and_admin(ProjectStatus.REVIEW)
        existing_user = UserFactory(email="admin_review@example.com")

        # Test via role assignment
        url = reverse("project-assign-roles", kwargs={"pk": project.pk})
        data = {
            "user_id": str(existing_user.id),
            "role": Role.PROJECT_ADMIN,
        }

        mail.outbox = []
        response = self.post(url, data=data, user=self.project_admin)
        self.assertEqual(response.status_code, 201)

        # Verify review email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Creation of the", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to[0], existing_user.email)

    def test_project_manager_receives_launch_email_when_added_to_ready_project(self):
        """
        Test that PROJECT_MANAGER receives launch email when added to project with READY status
        """
        project = self._create_project_with_status_and_admin(ProjectStatus.READY)
        existing_user = UserFactory(email="manager_ready@example.com")

        # Test via role assignment
        url = reverse("project-assign-roles", kwargs={"pk": project.pk})
        data = {
            "user_id": str(existing_user.id),
            "role": Role.PROJECT_MANAGER,
        }

        mail.outbox = []
        response = self.post(url, data=data, user=self.project_admin)
        self.assertEqual(response.status_code, 201)

        # Verify launch invitation email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Availability of the", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to[0], existing_user.email)

    @parameterized.expand(
        [
            (Role.PROJECT_ADMIN,),
            (Role.PROJECT_MANAGER,),
            (Role.INSTRUCTOR,),
            (Role.CONTROLLER,),
            (Role.GUEST,),
        ]
    )
    def test_any_role_receives_launched_email_when_added_to_launched_project(self, role):
        """
        Test that any role receives launched project email when added to project with LAUNCHED status
        """
        project = self._create_project_with_status_and_admin(ProjectStatus.LAUNCHED)
        existing_user = UserFactory(email=f"user_launched_{role.name.lower()}@example.com")

        # Test via role assignment
        url = reverse("project-assign-roles", kwargs={"pk": project.pk})
        data = {
            "user_id": str(existing_user.id),
            "role": role,
        }

        if role == Role.INSTRUCTOR:
            data["library_id"] = str(self.library.id)

        mail.outbox = []
        response = self.post(url, data=data, user=self.project_admin)
        self.assertEqual(response.status_code, 201)

        # Verify launched project email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Launch of the", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to[0], existing_user.email)


class TestEmailNotificationsForInvitationAndAccountCreation(TestCase):
    """
    Tests for email notifications when new users create accounts after invitation
    """

    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.project_admin = UserFactory()
            self.library = LibraryFactory()
            self.signer = _get_invite_signer()
            mail.outbox = []

    def _create_project_with_status_and_admin(self, status: ProjectStatus):
        """Helper to create a project with specific status and admin"""
        project = ProjectFactory(status=status)
        project.libraries.add(self.library)

        UserRole.objects.create(
            user=self.project_admin,
            project=project,
            role=Role.PROJECT_CREATOR,
            assigned_by=self.project_admin,
        )
        return project

    def test_new_project_admin_receives_review_email_after_account_creation_in_review_project(self):
        """
        Test that new PROJECT_ADMIN receives review email after creating account for REVIEW project
        """
        project = self._create_project_with_status_and_admin(ProjectStatus.REVIEW)
        new_user_email = "new_admin_review@example.com"

        # Add invitation
        invitation_data = {
            "email": new_user_email,
            "role": Role.PROJECT_ADMIN,
            "library_id": None,
        }
        project.invitations = [invitation_data]
        project.save()

        # Create account token
        token = self.signer.sign_object(
            {
                "email": new_user_email,
                "project_id": str(project.id),
                "invitations": [invitation_data],
                "assigned_by_id": str(self.project_admin.id),
            }
        )

        mail.outbox = []
        response = self.post(
            reverse("create_account"),
            {
                "token": token,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
            },
        )

        self.response_created(response)

        # Verify review email was sent
        self.assertEqual(len(mail.outbox), 2)  # Account creation + review email
        review_emails = [email for email in mail.outbox if "Creation of the" in email.subject]
        self.assertEqual(len(review_emails), 1)
        self.assertEqual(review_emails[0].to[0], new_user_email)

    def test_new_project_manager_receives_launch_email_after_account_creation_in_ready_project(self):
        """
        Test that new PROJECT_MANAGER receives launch email after creating account for READY project
        """
        project = self._create_project_with_status_and_admin(ProjectStatus.READY)
        new_user_email = "new_manager_ready@example.com"

        # Add invitation
        invitation_data = {
            "email": new_user_email,
            "role": Role.PROJECT_MANAGER,
            "library_id": None,
        }
        project.invitations = [invitation_data]
        project.save()

        # Create account token
        token = self.signer.sign_object(
            {
                "email": new_user_email,
                "project_id": str(project.id),
                "invitations": [invitation_data],
                "assigned_by_id": str(self.project_admin.id),
            }
        )

        mail.outbox = []
        response = self.post(
            reverse("create_account"),
            {
                "token": token,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
            },
        )

        self.response_created(response)

        # Verify launch email was sent
        self.assertEqual(len(mail.outbox), 2)  # Account creation + launch email
        launch_emails = [email for email in mail.outbox if "Availability of the" in email.subject]
        self.assertEqual(len(launch_emails), 1)
        self.assertEqual(launch_emails[0].to[0], new_user_email)

    @parameterized.expand(
        [
            (Role.PROJECT_ADMIN,),
            (Role.PROJECT_MANAGER,),
            (Role.INSTRUCTOR,),
            (Role.CONTROLLER,),
            (Role.GUEST,),
        ]
    )
    def test_new_user_receives_launched_email_after_account_creation_in_launched_project(self, role):
        """
        Test that new user with any role receives launched project email after creating account for LAUNCHED project
        """
        project = self._create_project_with_status_and_admin(ProjectStatus.LAUNCHED)
        new_user_email = f"new_user_launched_{role.name.lower()}@example.com"

        # Add invitation
        invitation_data = {
            "email": new_user_email,
            "role": role,
            "library_id": str(self.library.id) if role == Role.INSTRUCTOR else None,
        }
        project.invitations = [invitation_data]
        project.save()

        # Create account token
        token = self.signer.sign_object(
            {
                "email": new_user_email,
                "project_id": str(project.id),
                "invitations": [invitation_data],
                "assigned_by_id": str(self.project_admin.id),
            }
        )

        mail.outbox = []
        response = self.post(
            reverse("create_account"),
            {
                "token": token,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
            },
        )

        self.response_created(response)

        # Verify launched project email was sent
        self.assertEqual(len(mail.outbox), 2)  # Account creation + launched email
        launched_emails = [email for email in mail.outbox if "Launch of the" in email.subject]
        self.assertEqual(len(launched_emails), 1)
        self.assertEqual(launched_emails[0].to[0], new_user_email)


class TestInvitationWorkflowIntegration(TestCase):
    """
    Integration tests for the complete invitation workflow
    """

    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.project_admin = UserFactory()
            self.library = LibraryFactory()
            self.signer = _get_invite_signer()
            mail.outbox = []

    def _create_project_with_status_and_admin(self, status: ProjectStatus):
        """Helper to create a project with specific status and admin"""
        project = ProjectFactory(status=status)
        project.libraries.add(self.library)

        UserRole.objects.create(
            user=self.project_admin,
            project=project,
            role=Role.PROJECT_CREATOR,
            assigned_by=self.project_admin,
        )
        return project

    @parameterized.expand(
        [
            (ProjectStatus.REVIEW, Role.PROJECT_ADMIN, "Creation of the"),
            (ProjectStatus.READY, Role.PROJECT_MANAGER, "Availability of the"),
            (ProjectStatus.LAUNCHED, Role.GUEST, "Launch of the"),
        ]
    )
    def test_complete_invitation_workflow_for_non_draft_projects(self, project_status, role, expected_email_subject):
        """
        Test complete workflow: invitation -> immediate email -> account creation -> appropriate notification
        """
        project = self._create_project_with_status_and_admin(project_status)
        new_user_email = f"workflow_test_{project_status.name.lower()}@example.com"

        # Step 1: Send invitation
        url = reverse("project-add-invitation", kwargs={"pk": project.pk})
        data = {
            "email": new_user_email,
            "role": role,
        }

        mail.outbox = []
        response = self.post(url, data=data, user=self.project_admin)
        self.assertEqual(response.status_code, 201)

        # Verify invitation email was sent immediately
        self.assertEqual(len(mail.outbox), 1)
        invitation_email = mail.outbox[0]
        self.assertIn("creating your account", invitation_email.subject.lower())  # Correction ici

        # Step 2: User creates account
        project.refresh_from_db()
        invitation_data = next(inv for inv in project.invitations if inv.get("email") == new_user_email)

        token = self.signer.sign_object(
            {
                "email": new_user_email,
                "project_id": str(project.id),
                "invitations": [invitation_data],
                "assigned_by_id": str(self.project_admin.id),
            }
        )

        mail.outbox = []
        create_account_response = self.post(
            reverse("create_account"),
            {
                "token": token,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
            },
        )

        self.response_created(create_account_response)

        # Verify appropriate notification email was sent
        notification_emails = [email for email in mail.outbox if expected_email_subject in email.subject]
        self.assertEqual(len(notification_emails), 1)
        self.assertEqual(notification_emails[0].to[0], new_user_email)

        # Verify user role was created
        new_user = User.objects.get(email=new_user_email)
        user_role = UserRole.objects.get(user=new_user, project=project, role=role)
        self.assertEqual(user_role.assigned_by, self.project_admin)

        # Verify invitations were cleaned up
        project.refresh_from_db()
        remaining_emails = [inv.get("email") for inv in (project.invitations or [])]
        self.assertNotIn(new_user_email, remaining_emails)
