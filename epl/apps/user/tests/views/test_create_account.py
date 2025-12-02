from unittest.mock import patch

from django.core import mail  # <-- 1. AJOUTEZ CET IMPORT
from django.utils.translation import gettext_lazy as _
from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context
from rest_framework import status

from epl.apps.project.models import Role, UserRole
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import UserFactory
from epl.apps.user.models import User
from epl.apps.user.views import _get_invite_signer
from epl.tests import TestCase


class TestCreateAccountView(TestCase):
    def test_successful_account_creation(self):
        signer = _get_invite_signer()
        email = "new_user@example.com"
        token = signer.sign_object({"email": email})

        response = self.post(
            reverse("create_account"),
            {
                "token": token,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
                "first_name": "John",
                "last_name": "Doe",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        with tenant_context(self.tenant):
            user = User.objects.get(email=email)
            self.assertTrue(User.objects.filter(email=email).exists())
            self.assertEqual(user.first_name, "John")
            self.assertEqual(user.last_name, "Doe")

    def test_password_mismatch(self):
        signer = _get_invite_signer()
        email = "new_user@example.com"
        token = signer.sign_object({"email": email})

        response = self.post(
            reverse("create_account"),
            {
                "token": token,
                "password": "SecurePassword123!",
                "confirm_password": "DifferentPassword123!",
                "first_name": "John",
                "last_name": "Doe",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Password and confirm password do not match", str(response.content))

    def test_invalid_token(self):
        response = self.post(
            reverse("create_account"),
            {
                "token": "invalid_token",
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
                "first_name": "John",
                "last_name": "Doe",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue("invalid invite token" in str(response.content).lower())

    def test_expired_token(self):
        signer = _get_invite_signer()
        email = "new_user@example.com"
        token = signer.sign_object({"email": email})

        with patch("epl.apps.user.views.INVITE_TOKEN_MAX_AGE", 0):
            response = self.post(
                reverse("create_account"),
                {
                    "token": token,
                    "password": "SecurePassword123!",
                    "confirm_password": "SecurePassword123!",
                    "first_name": "John",
                    "last_name": "Doe",
                },
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invite token expired", str(response.content))

    def test_account_creation_sends_confirmation_email(self):
        signer = _get_invite_signer()
        email = "new_user_for_email_test@example.com"
        token = signer.sign_object({"email": email})
        mail.outbox = []

        response = self.post(
            reverse("create_account"),
            {
                "token": token,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
                "first_name": "John",
                "last_name": "Doe",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(len(mail.outbox), 1)

        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.to, [email])
        expected_subject_string = str(_("your account creation"))
        expected_body_string = str(_("Your account has just been opened"))

        self.assertIn(expected_subject_string, sent_email.subject)
        self.assertIn(expected_body_string, sent_email.body)

        self.assertIn(email, sent_email.body)

    def test_account_creation_without_names(self):
        """Test that account creation works without first_name and last_name"""
        signer = _get_invite_signer()
        email = "new_user@example.com"
        token = signer.sign_object({"email": email})

        response = self.post(
            reverse("create_account"),
            {
                "token": token,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
                "first_name": "John",
                "last_name": "Doe",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        with tenant_context(self.tenant):
            user = User.objects.get(email=email)
            self.assertTrue(User.objects.filter(email=email).exists())
            # User exists but first_name and last_name are empty strings
            self.assertEqual(user.first_name, "John")
            self.assertEqual(user.last_name, "Doe")

    def test_account_creation_with_empty_names(self):
        """Test that account creation works with empty first_name and last_name"""
        signer = _get_invite_signer()
        email = "new_user@example.com"
        token = signer.sign_object({"email": email})

        response = self.post(
            reverse("create_account"),
            {
                "token": token,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
                "first_name": "John",
                "last_name": "Doe",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        with tenant_context(self.tenant):
            user = User.objects.get(email=email)
            self.assertEqual(user.first_name, "John")
            self.assertEqual(user.last_name, "Doe")


class TestAccountCreationWithExistingUser(TestCase):
    """
    Tests for account creation when the user already exists in the database.
    """

    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            # Create a project creator and a project
            self.project_creator = UserFactory()
            self.project = ProjectFactory()
            UserRole.objects.create(
                user=self.project_creator,
                project=self.project,
                role=Role.PROJECT_CREATOR,
                assigned_by=self.project_creator,
            )

            # Create a library
            self.library = LibraryFactory()
            self.project.libraries.add(self.library)

            # Create an existing user
            self.existing_user = UserFactory(email="existing@example.com")

            # Create signer
            self.signer = _get_invite_signer()

    def test_existing_user_gets_roles_assigned_no_new_account(self):
        """
        Test that when an existing user clicks the invitation link:
        1. No new account is created
        2. Roles are assigned to existing user
        3. No account creation email is sent
        """
        # Add invitation for existing user
        invitation_data = {
            "email": self.existing_user.email,
            "role": Role.PROJECT_ADMIN,
            "library_id": None,
        }
        self.project.invitations = [invitation_data]
        self.project.save()

        # Create token
        token = self.signer.sign_object(
            {
                "email": self.existing_user.email,
                "project_id": str(self.project.id),
                "invitations": [invitation_data],
                "assigned_by_id": str(self.project_creator.id),
            }
        )

        with patch("epl.services.user.email.send_account_created_email") as mock_send_email:
            response = self.post(
                reverse("create_account"),
                {
                    "token": token,
                    "password": "SecurePassword123!",
                    "confirm_password": "SecurePassword123!",
                    "first_name": "Jane",
                    "last_name": "Smith",
                },
            )

        self.response_created(response)

        # Verify no new user was created (still only one user with this email)
        users_with_email = User.objects.filter(email=self.existing_user.email)
        self.assertEqual(users_with_email.count(), 1)

        # Verify it's the same user (not a new one)
        self.assertEqual(users_with_email.first().id, self.existing_user.id)

        # Verify no account creation email was sent
        mock_send_email.assert_not_called()

        # Verify role was assigned
        user_role = UserRole.objects.get(user=self.existing_user, project=self.project, role=Role.PROJECT_ADMIN)
        self.assertEqual(user_role.assigned_by, self.project_creator)

        # Verify invitation was removed
        self.project.refresh_from_db()
        self.assertEqual(len(self.project.invitations), 0)

        # Verify first_name and last_name weren't changed for existing user
        self.existing_user.refresh_from_db()
        self.assertNotEqual(self.existing_user.first_name, "Jane")
        self.assertNotEqual(self.existing_user.last_name, "Smith")

    def test_existing_user_multiple_roles(self):
        """
        Test existing user getting multiple roles assigned.
        """
        invitations_data = [
            {
                "email": self.existing_user.email,
                "role": Role.INSTRUCTOR,
                "library_id": str(self.library.id),
            },
            {
                "email": self.existing_user.email,
                "role": Role.CONTROLLER,
                "library_id": None,
            },
        ]
        self.project.invitations = invitations_data
        self.project.save()

        token = self.signer.sign_object(
            {
                "email": self.existing_user.email,
                "project_id": str(self.project.id),
                "invitations": invitations_data,
                "assigned_by_id": str(self.project_creator.id),
            }
        )

        response = self.post(
            reverse("create_account"),
            {
                "token": token,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
                "first_name": "Jane",
                "last_name": "Smith",
            },
        )

        self.response_created(response)

        # Verify both roles were assigned
        user_roles = UserRole.objects.filter(user=self.existing_user, project=self.project)
        self.assertEqual(user_roles.count(), 2)

        roles = [ur.role for ur in user_roles]
        self.assertIn(Role.INSTRUCTOR, roles)
        self.assertIn(Role.CONTROLLER, roles)

        # Verify instructor role has library
        instructor_role = user_roles.get(role=Role.INSTRUCTOR)
        self.assertEqual(instructor_role.library, self.library)

    def test_existing_user_with_existing_role_succeeds_without_duplicate(self):
        """
        Test that when an existing user already has a role and clicks invitation link,
        the process succeeds but no duplicate role is created.
        """
        # Create existing role
        existing_role = UserRole.objects.create(
            user=self.existing_user,
            project=self.project,
            role=Role.PROJECT_ADMIN,
            assigned_by=self.project_creator,
        )

        # Count roles before
        initial_role_count = UserRole.objects.filter(
            user=self.existing_user, project=self.project, role=Role.PROJECT_ADMIN
        ).count()
        self.assertEqual(initial_role_count, 1)

        # Create invitation for same role
        invitation_data = {
            "email": self.existing_user.email,
            "role": Role.PROJECT_ADMIN,
            "library_id": None,
        }
        self.project.invitations = [invitation_data]
        self.project.save()

        token = self.signer.sign_object(
            {
                "email": self.existing_user.email,
                "project_id": str(self.project.id),
                "invitations": [invitation_data],
                "assigned_by_id": str(self.project_creator.id),
            }
        )

        response = self.post(
            reverse("create_account"),
            {
                "token": token,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
                "first_name": "Jane",
                "last_name": "Smith",
            },
        )

        # Process should succeed
        self.response_created(response)

        # But verify NO duplicate was created (still only 1 role)
        final_role_count = UserRole.objects.filter(
            user=self.existing_user, project=self.project, role=Role.PROJECT_ADMIN
        ).count()
        self.assertEqual(final_role_count, 1)  # Still only 1

        # Verify it's the same original role
        self.assertEqual(
            UserRole.objects.get(user=self.existing_user, project=self.project, role=Role.PROJECT_ADMIN).id,
            existing_role.id,
        )

        # Verify invitation was still cleaned up
        self.project.refresh_from_db()
        remaining_invitations = [
            inv for inv in (self.project.invitations or []) if inv.get("email") == self.existing_user.email
        ]
        self.assertEqual(len(remaining_invitations), 0)

    def test_inactive_existing_user_invitation_fails(self):
        """
        Test that invitation fails if an inactive user exists with the same email.
        """
        # Create inactive user
        inactive_user = UserFactory(email="inactive@example.com", is_active=False)

        invitation_data = {
            "email": inactive_user.email,
            "role": Role.PROJECT_ADMIN,
            "library_id": None,
        }
        self.project.invitations = [invitation_data]
        self.project.save()

        token = self.signer.sign_object(
            {
                "email": inactive_user.email,
                "project_id": str(self.project.id),
                "invitations": [invitation_data],
                "assigned_by_id": str(self.project_creator.id),
            }
        )

        response = self.post(
            reverse("create_account"),
            {
                "token": token,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
                "first_name": "Jane",
                "last_name": "Smith",
            },
        )

        # Should fail with 400
        self.response_bad_request(response)
        self.assertIn("inactive user account exists", str(response.content).lower())

        # Verify no new user was created
        users_with_email = User.objects.filter(email=inactive_user.email)
        self.assertEqual(users_with_email.count(), 1)  # Only the original inactive user

        # Verify no role was assigned to the inactive user
        self.assertFalse(UserRole.objects.filter(user=inactive_user, project=self.project).exists())

        # Verify inactive user is still inactive
        inactive_user.refresh_from_db()
        self.assertFalse(inactive_user.is_active)

    def test_password_ignored_for_existing_user(self):
        """
        Test that password in the request is ignored for existing users.
        """
        # Store original password hash
        original_password = self.existing_user.password

        invitation_data = {
            "email": self.existing_user.email,
            "role": Role.PROJECT_ADMIN,
            "library_id": None,
        }
        self.project.invitations = [invitation_data]
        self.project.save()

        token = self.signer.sign_object(
            {
                "email": self.existing_user.email,
                "project_id": str(self.project.id),
                "invitations": [invitation_data],
                "assigned_by_id": str(self.project_creator.id),
            }
        )

        response = self.post(
            reverse("create_account"),
            {
                "token": token,
                "password": "NewPassword123!",
                "confirm_password": "NewPassword123!",
                "first_name": "Jane",
                "last_name": "Smith",
            },
        )

        self.response_created(response)

        # Verify password wasn't changed
        self.existing_user.refresh_from_db()
        self.assertEqual(self.existing_user.password, original_password)

        # Verify role was still assigned
        self.assertTrue(
            UserRole.objects.filter(user=self.existing_user, project=self.project, role=Role.PROJECT_ADMIN).exists()
        )
