import uuid
from unittest.mock import patch
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context
from parameterized import parameterized

from epl.apps.project.models import Role, UserRole
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import UserFactory, UserWithRoleFactory
from epl.apps.user.models import User
from epl.apps.user.views import _get_invite_signer
from epl.tests import TestCase


class TestUserAccountCreationAfterInviteSingleRole(TestCase):
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

            # Add an invitation for a new project admin user
            self.invitation_data = {
                "email": "new_project_admin@example.com",
                "role": Role.PROJECT_ADMIN,
                "library_id": None,
            }

            # Add the invitation to the project
            self.project.invitations.append(self.invitation_data)
            self.project.save()

            # Create the token from the invitation data
            self.signer = _get_invite_signer()
            self.new_user_email = self.invitation_data["email"]
            self.token = self.signer.sign_object(
                {
                    "email": self.invitation_data["email"],
                    "project_id": str(self.project.id),
                    "invitations": [self.invitation_data],
                    "assigned_by_id": str(self.project_creator.id),
                }
            )

    def test_account_creation_with_invitation_success(self):
        response = self.post(
            reverse("create_account"),
            {"token": self.token, "password": "SecurePassword123!", "confirm_password": "SecurePassword123!"},
        )

        self.response_created(response)

        # Verify user creation
        self.assertTrue(User.objects.filter(email=self.new_user_email).exists())
        new_user = User.objects.get(email=self.new_user_email)
        user_role = UserRole.objects.get(user=new_user, project=self.project)
        self.assertEqual(user_role.role, Role.PROJECT_ADMIN)
        self.assertEqual(user_role.assigned_by, self.project_creator)

        # Verify invitation was removed
        self.project.refresh_from_db()
        self.assertEqual(len(self.project.invitations), 0)

    def test_password_mismatch(self):
        response = self.post(
            reverse("create_account"),
            {"token": self.token, "password": "SecurePassword123!", "confirm_password": "DifferentPassword123!"},
        )
        self.response_bad_request(response)
        self.assertIn("Password and confirm password do not match", str(response.content))

    def test_account_creation_with_invitation_fails_with_invalid_token(self):
        invalid_token = "invalid_token"  # noqa S105
        response = self.post(
            reverse("create_account"),
            {"token": invalid_token, "password": "SecurePassword123!", "confirm_password": "SecurePassword123!"},
        )
        self.response_bad_request(response)

    def test_account_creation_with_expired_token(self):
        with patch("epl.apps.user.views.INVITE_TOKEN_MAX_AGE", 0):
            response = self.post(
                reverse("create_account"),
                {"token": self.token, "password": "SecurePassword123!", "confirm_password": "SecurePassword123!"},
            )
        self.response_bad_request(response)
        self.assertIn("Invite token expired", str(response.content))

    def test_account_creation_fails_with_weak_password(self):
        with patch("django.contrib.auth.password_validation.validate_password") as mock_validate:
            mock_validate.side_effect = ValidationError("The password is too weak.")
            response = self.post(
                reverse("create_account"),
                {"token": self.token, "password": "weak", "confirm_password": "weak"},  # noqa S105
            )
        self.response_bad_request(response)
        self.assertIn("The password is too weak", str(response.content))

    def test_account_creation_fails_with_project_not_found(self):
        token_with_invalid_project = self.signer.sign_object(
            {
                "email": self.new_user_email,
                "project_id": str(uuid.uuid4()),  # Non-existent project
                "invitations": [self.invitation_data],
                "assigned_by_id": str(self.project_creator.id),
            }
        )
        response = self.post(
            reverse("create_account"),
            {
                "token": token_with_invalid_project,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
            },
        )
        self.response_bad_request(response)
        self.assertIn("The project associated with this invitation no longer exists", str(response.content))

    def test_account_creation_fails_with_assigner_not_found(self):
        token_with_invalid_assigner = self.signer.sign_object(
            {
                "email": self.new_user_email,
                "project_id": str(self.project.id),
                "invitations": [self.invitation_data],
                "assigned_by_id": str(uuid.uuid4()),  # Non-existent assigner
            }
        )
        response = self.post(
            reverse("create_account"),
            {
                "token": token_with_invalid_assigner,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
            },
        )
        self.response_bad_request(response)
        self.assertIn("Invitation expired. The user who sent the invitation no longer exists", str(response.content))

    def test_account_creation_success_without_library(self):
        invitation_without_library = {
            "email": self.new_user_email,
            "role": Role.PROJECT_ADMIN,
            "library_id": None,
        }

        token_without_library = self.signer.sign_object(
            {
                "email": self.new_user_email,
                "project_id": str(self.project.id),
                "invitations": [invitation_without_library],
                "assigned_by_id": str(self.project_creator.id),
            }
        )

        response = self.post(
            reverse("create_account"),
            {
                "token": token_without_library,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
            },
        )

        self.response_created(response)

        self.assertTrue(User.objects.filter(email=self.new_user_email).exists())
        new_user = User.objects.get(email=self.new_user_email)
        user_role = UserRole.objects.get(user=new_user, project=self.project)
        self.assertEqual(user_role.role, Role.PROJECT_ADMIN)
        self.assertEqual(user_role.assigned_by, self.project_creator)

    def test_account_creation_fails_without_email_in_token(self):
        token_without_email = self.signer.sign_object(
            {
                # No email specified
                "project_id": str(self.project.id),
                "invitations": [{"role": Role.PROJECT_ADMIN, "library_id": None}],
                "assigned_by_id": str(self.project_creator.id),
            }
        )

        response = self.post(
            reverse("create_account"),
            {"token": token_without_email, "password": "SecurePassword123!", "confirm_password": "SecurePassword123!"},
        )
        self.response_bad_request(response)

    def test_account_creation_fails_with_library_not_found(self):
        invitation_with_invalid_library = {
            "email": self.new_user_email,
            "role": Role.PROJECT_ADMIN,
            "library_id": str(uuid.uuid4()),
        }

        token_with_invalid_library = self.signer.sign_object(
            {
                "email": self.new_user_email,
                "project_id": str(self.project.id),
                "invitations": [invitation_with_invalid_library],  # ← Nouveau format
                "assigned_by_id": str(self.project_creator.id),
            }
        )

        response = self.post(
            reverse("create_account"),
            {
                "token": token_with_invalid_library,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
            },
        )

        self.response_bad_request(response)

    def test_account_creation_fails_when_no_email_in_project_invitation(self):
        non_invited_invitation = {
            "email": "not_invited@example.com",
            "role": Role.PROJECT_ADMIN,
            "library_id": None,
        }

        token_with_non_invited_email = self.signer.sign_object(
            {
                "email": "not_invited@example.com",
                "project_id": str(self.project.id),
                "invitations": [non_invited_invitation],
                "assigned_by_id": str(self.project_creator.id),
            }
        )

        response = self.post(
            reverse("create_account"),
            {
                "token": token_with_non_invited_email,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
            },
        )

        self.response_bad_request(response)
        self.assertIn("This email is not invited to join this project", str(response.content))


class TestUserAccountCreationAfterInviteMultipleRoles(TestCase):
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

            # Create a library for the instructor role
            self.library = LibraryFactory()
            self.project.libraries.add(self.library)

            # Create multiple invitations for the same user (multiple roles)
            self.new_user_email = "multi_role_user@example.com"
            self.invitations_data = [
                {
                    "email": self.new_user_email,
                    "role": Role.INSTRUCTOR,
                    "library_id": str(self.library.id),
                },
                {
                    "email": self.new_user_email,
                    "role": Role.CONTROLLER,
                    "library_id": None,
                },
            ]

            # Add all invitations to the project
            for invitation in self.invitations_data:
                self.project.invitations.append(invitation)
            self.project.save()

            # Create the token with multiple invitations
            self.signer = _get_invite_signer()
            self.token = self.signer.sign_object(
                {
                    "email": self.new_user_email,
                    "project_id": str(self.project.id),
                    "invitations": self.invitations_data,  # Multiple invitations
                    "assigned_by_id": str(self.project_creator.id),
                }
            )

    def test_account_creation_with_multiple_roles_success(self):
        """Test creating account when user has multiple roles (INSTRUCTOR + CONTROLLER)."""
        response = self.post(
            reverse("create_account"),
            {"token": self.token, "password": "SecurePassword123!", "confirm_password": "SecurePassword123!"},
        )

        self.response_created(response)

        # Verify user creation
        self.assertTrue(User.objects.filter(email=self.new_user_email).exists())
        new_user = User.objects.get(email=self.new_user_email)

        # Verify ALL roles were created
        user_roles = UserRole.objects.filter(user=new_user, project=self.project)
        self.assertEqual(user_roles.count(), 2, "Should create exactly 2 roles")

        # Verify specific roles exist
        roles = [ur.role for ur in user_roles]
        self.assertIn(Role.INSTRUCTOR, roles, "Should have INSTRUCTOR role")
        self.assertIn(Role.CONTROLLER, roles, "Should have CONTROLLER role")

        # Verify the instructor role has the correct library
        instructor_role = user_roles.get(role=Role.INSTRUCTOR)
        self.assertEqual(instructor_role.library, self.library)
        self.assertEqual(instructor_role.assigned_by, self.project_creator)

        # Verify the controller role has no library
        controller_role = user_roles.get(role=Role.CONTROLLER)
        self.assertIsNone(controller_role.library)
        self.assertEqual(controller_role.assigned_by, self.project_creator)

        # Verify ALL invitations for this email were removed
        self.project.refresh_from_db()
        remaining_emails = [inv.get("email") for inv in self.project.invitations]
        self.assertNotIn(self.new_user_email, remaining_emails)
        self.assertEqual(len(self.project.invitations), 0)

    def test_multiple_roles_with_three_roles(self):
        """Test with 3 roles: INSTRUCTOR, CONTROLLER, GUEST."""
        # Add a third role
        guest_invitation = {
            "email": self.new_user_email,
            "role": Role.GUEST,
            "library_id": None,
        }
        self.invitations_data.append(guest_invitation)
        self.project.invitations.append(guest_invitation)
        self.project.save()

        # Create new token with 3 roles
        token_with_three_roles = self.signer.sign_object(
            {
                "email": self.new_user_email,
                "project_id": str(self.project.id),
                "invitations": self.invitations_data,  # 3 invitations
                "assigned_by_id": str(self.project_creator.id),
            }
        )

        response = self.post(
            reverse("create_account"),
            {
                "token": token_with_three_roles,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
            },
        )

        self.response_created(response)

        # Verify user creation
        new_user = User.objects.get(email=self.new_user_email)

        # Verify ALL 3 roles were created
        user_roles = UserRole.objects.filter(user=new_user, project=self.project)
        self.assertEqual(user_roles.count(), 3)

        # Verify specific roles
        roles = [ur.role for ur in user_roles]
        expected_roles = [Role.INSTRUCTOR, Role.CONTROLLER, Role.GUEST]
        self.assertCountEqual(roles, expected_roles)

    def test_empty_invitations_list(self):
        """Test behavior with empty invitations list."""
        empty_token = self.signer.sign_object(
            {
                "email": self.new_user_email,
                "project_id": str(self.project.id),
                "invitations": [],  # Empty list
                "assigned_by_id": str(self.project_creator.id),
            }
        )

        response = self.post(
            reverse("create_account"),
            {"token": empty_token, "password": "SecurePassword123!", "confirm_password": "SecurePassword123!"},
        )

        self.response_created(response)

        # Verify user created but no roles assigned
        new_user = User.objects.get(email=self.new_user_email)
        user_roles = UserRole.objects.filter(user=new_user, project=self.project)
        self.assertEqual(user_roles.count(), 0)


class ProjectInvitationTests(TestCase):
    """
    Tests for project invitation endpoints.
    """

    def setUp(self):
        """
        Set up the test case.
        """
        super().setUp()
        with tenant_context(self.tenant):
            self.project = ProjectFactory()
            self.library = LibraryFactory()

    @parameterized.expand(
        [
            (Role.PROJECT_CREATOR, True, 201),
            (Role.PROJECT_ADMIN, True, 201),
            (Role.PROJECT_MANAGER, False, 403),
            (Role.INSTRUCTOR, False, 403),
            (Role.CONTROLLER, False, 403),
            (Role.GUEST, False, 403),
            (None, False, 403),
        ]
    )
    def test_add_invitation_permissions(self, role, should_succeed, expected_status):
        user = UserWithRoleFactory(role=role, project=self.project, library=self.library)
        url = reverse("project-add-invitation", kwargs={"pk": self.project.pk})

        data = {
            "email": "newuser@example.com",
            "role": Role.GUEST,
        }
        response = self.post(url, data=data, user=user)
        self.assertEqual(response.status_code, expected_status)

        if should_succeed:
            self.project.refresh_from_db()
            self.assertEqual(len(self.project.invitations), 1)
            self.assertEqual(self.project.invitations[0]["email"], "newuser@example.com")
            self.assertEqual(self.project.invitations[0]["role"], Role.GUEST)

    @parameterized.expand(
        [
            (Role.PROJECT_CREATOR, True, 204),
            (Role.PROJECT_ADMIN, True, 204),
            (Role.PROJECT_MANAGER, False, 403),
            (Role.INSTRUCTOR, False, 403),
            (Role.CONTROLLER, False, 403),
            (Role.GUEST, False, 403),
            (None, False, 403),
        ]
    )
    def test_remove_invitation_permissions(self, role, should_succeed, expected_status):
        user = UserWithRoleFactory(role=role, project=self.project, library=self.library)

        admin = UserWithRoleFactory(role=Role.PROJECT_ADMIN, project=self.project)
        url_add = reverse("project-add-invitation", kwargs={"pk": self.project.pk})
        data = {"email": "toremove@example.com", "role": Role.GUEST}
        self.post(url_add, data=data, user=admin)

        # Verify that the invitation was added
        self.project.refresh_from_db()
        self.assertEqual(len(self.project.invitations), 1)

        query_string = urlencode(data)  # Prepare the query string for the deletion URL
        url_remove = reverse("project-add-invitation", kwargs={"pk": self.project.pk}) + f"?{query_string}"
        response = self.delete(url_remove, user=user)
        self.assertEqual(response.status_code, expected_status)

        if should_succeed:
            self.project.refresh_from_db()
            self.assertEqual(len(self.project.invitations), 0)
        else:
            self.project.refresh_from_db()
            self.assertEqual(len(self.project.invitations), 1)


class TestInviteExistingUsers(TestCase):
    """
    Tests for the behavior when inviting users who already exist in the database.
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

            # Create a library for instructor roles
            self.library = LibraryFactory()
            self.project.libraries.add(self.library)

            # Create an existing user in the database
            self.existing_user = UserFactory(email="existing@example.com")

    @patch("epl.services.project.notifications.send_invite_to_epl_email")
    def test_existing_user_not_sent_email_and_gets_role_assigned(self, mock_send_email):
        """
        Test that when inviting an existing user:
        1. No email is sent
        2. UserRole is created directly
        """
        from epl.services.project.notifications import invite_unregistered_users_to_epl

        # Add invitation for existing user
        invitation_data = {
            "email": self.existing_user.email,
            "role": Role.PROJECT_ADMIN,
            "library_id": None,
        }
        self.project.invitations = [invitation_data]
        self.project.save()

        # Create a mock request
        class MockRequest:
            def __init__(self, user):
                self.user = user

        mock_request = MockRequest(self.project_creator)

        # Call the function
        invite_unregistered_users_to_epl(self.project, mock_request)

        # Verify no email was sent
        mock_send_email.assert_not_called()

        # Verify UserRole was created for the existing user
        user_role = UserRole.objects.get(user=self.existing_user, project=self.project, role=Role.PROJECT_ADMIN)
        self.assertEqual(user_role.assigned_by, self.project_creator)
        self.assertIsNone(user_role.library_id)

    @patch("epl.services.project.notifications.send_invite_to_epl_email")
    def test_existing_user_with_library_role(self, mock_send_email):
        """
        Test that existing user gets instructor role with library assigned.
        """
        from epl.services.project.notifications import invite_unregistered_users_to_epl

        # Add invitation for existing user as instructor
        invitation_data = {
            "email": self.existing_user.email,
            "role": Role.INSTRUCTOR,
            "library_id": str(self.library.id),
        }
        self.project.invitations = [invitation_data]
        self.project.save()

        class MockRequest:
            def __init__(self, user):
                self.user = user

        mock_request = MockRequest(self.project_creator)

        # Call the function
        invite_unregistered_users_to_epl(self.project, mock_request)

        # Verify no email was sent
        mock_send_email.assert_not_called()

        # Verify UserRole was created with library
        user_role = UserRole.objects.get(user=self.existing_user, project=self.project, role=Role.INSTRUCTOR)
        self.assertEqual(user_role.library_id, self.library.id)
        self.assertEqual(user_role.assigned_by, self.project_creator)

    @patch("epl.services.project.notifications.send_invite_to_epl_email")
    def test_existing_user_multiple_roles(self, mock_send_email):
        """
        Test that existing user gets multiple roles assigned without email.
        """
        from epl.services.project.notifications import invite_unregistered_users_to_epl

        # Add multiple invitations for the same existing user
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

        class MockRequest:
            def __init__(self, user):
                self.user = user

        mock_request = MockRequest(self.project_creator)

        # Call the function
        invite_unregistered_users_to_epl(self.project, mock_request)

        # Verify no email was sent
        mock_send_email.assert_not_called()

        # Verify both UserRoles were created
        user_roles = UserRole.objects.filter(user=self.existing_user, project=self.project)
        self.assertEqual(user_roles.count(), 2)

        # Check specific roles
        instructor_role = user_roles.get(role=Role.INSTRUCTOR)
        self.assertEqual(instructor_role.library_id, self.library.id)

        controller_role = user_roles.get(role=Role.CONTROLLER)
        self.assertIsNone(controller_role.library_id)

        # Both should be assigned by project creator
        for user_role in user_roles:
            self.assertEqual(user_role.assigned_by, self.project_creator)

    @patch("epl.services.project.notifications.send_invite_to_epl_email")
    def test_mixed_existing_and_new_users(self, mock_send_email):
        """
        Test behavior with both existing and non-existing users:
        - Existing user: no email, role assigned
        - Non-existing user: email sent, no role assigned yet
        """
        from epl.services.project.notifications import invite_unregistered_users_to_epl

        # Invitations for both existing and new users
        invitations_data = [
            {
                "email": self.existing_user.email,  # Existing user
                "role": Role.PROJECT_ADMIN,
                "library_id": None,
            },
            {
                "email": "newuser@example.com",  # New user
                "role": Role.GUEST,
                "library_id": None,
            },
        ]
        self.project.invitations = invitations_data
        self.project.save()

        class MockRequest:
            def __init__(self, user):
                self.user = user

        mock_request = MockRequest(self.project_creator)

        # Call the function
        invite_unregistered_users_to_epl(self.project, mock_request)

        # Verify email was sent only once (for the new user)
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args[1]  # Get keyword arguments
        self.assertEqual(call_args["email"], "newuser@example.com")

        # Verify existing user got role assigned
        user_role = UserRole.objects.get(user=self.existing_user, project=self.project)
        self.assertEqual(user_role.role, Role.PROJECT_ADMIN)

        # Verify new user doesn't have role yet (would be created on account creation)
        self.assertFalse(UserRole.objects.filter(user__email="newuser@example.com", project=self.project).exists())

    @patch("epl.services.project.notifications.send_invite_to_epl_email")
    def test_existing_user_duplicate_role_not_created(self, mock_send_email):
        """
        Test that if an existing user already has a role, it's not duplicated.
        """
        from epl.services.project.notifications import invite_unregistered_users_to_epl

        # Create an existing UserRole
        existing_role = UserRole.objects.create(
            user=self.existing_user,
            project=self.project,
            role=Role.PROJECT_ADMIN,
            assigned_by=self.project_creator,
        )

        # Add invitation for the same role
        invitation_data = {
            "email": self.existing_user.email,
            "role": Role.PROJECT_ADMIN,
            "library_id": None,
        }
        self.project.invitations = [invitation_data]
        self.project.save()

        class MockRequest:
            def __init__(self, user):
                self.user = user

        mock_request = MockRequest(self.project_creator)

        # Call the function
        invite_unregistered_users_to_epl(self.project, mock_request)

        # Verify no email was sent
        mock_send_email.assert_not_called()

        # Verify only one UserRole exists (no duplicate created)
        user_roles = UserRole.objects.filter(user=self.existing_user, project=self.project, role=Role.PROJECT_ADMIN)
        self.assertEqual(user_roles.count(), 1)
        self.assertEqual(user_roles.first().id, existing_role.id)

    @patch("epl.services.project.notifications.send_invite_to_epl_email")
    def test_inactive_user_still_gets_email(self, mock_send_email):
        """
        Test that inactive users are treated as non-existing and get email invitations.
        """
        from epl.services.project.notifications import invite_unregistered_users_to_epl

        # Create an inactive user
        inactive_user = UserFactory(email="inactive@example.com", is_active=False)

        # Add invitation for inactive user
        invitation_data = {
            "email": inactive_user.email,
            "role": Role.PROJECT_ADMIN,
            "library_id": None,
        }
        self.project.invitations = [invitation_data]
        self.project.save()

        class MockRequest:
            def __init__(self, user):
                self.user = user

        mock_request = MockRequest(self.project_creator)

        # Call the function
        invite_unregistered_users_to_epl(self.project, mock_request)

        # Verify email was sent (inactive user treated as non-existing)
        mock_send_email.assert_called_once()

        # Verify no UserRole was created for inactive user
        self.assertFalse(UserRole.objects.filter(user=inactive_user, project=self.project).exists())
