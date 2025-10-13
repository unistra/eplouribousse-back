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

    def test_multiple_roles_with_invalid_library(self):
        """Test that creation fails if one of the roles has an invalid library."""
        # Modify one invitation to have invalid library
        invalid_invitations = [
            {
                "email": self.new_user_email,
                "role": Role.INSTRUCTOR,
                "library_id": str(uuid.uuid4()),  # Invalid library ID
            },
            {
                "email": self.new_user_email,
                "role": Role.CONTROLLER,
                "library_id": None,
            },
        ]

        token_with_invalid_library = self.signer.sign_object(
            {
                "email": self.new_user_email,
                "project_id": str(self.project.id),
                "invitations": invalid_invitations,
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
        self.assertIn("The library associated with this invitation no longer exists", str(response.content))

        # Verify no user was created (transaction rollback)
        self.assertFalse(User.objects.filter(email=self.new_user_email).exists())

    def test_multiple_roles_partial_invitations_in_project(self):
        """Test when only some invitations exist in project.invitations."""
        # Remove one invitation from project.invitations
        self.project.invitations = [self.invitations_data[0]]  # Only instructor
        self.project.save()

        response = self.post(
            reverse("create_account"),
            {"token": self.token, "password": "SecurePassword123!", "confirm_password": "SecurePassword123!"},
        )

        # Should still succeed because we check if email exists in invitations, not specific roles
        self.response_created(response)

        new_user = User.objects.get(email=self.new_user_email)
        user_roles = UserRole.objects.filter(user=new_user, project=self.project)
        self.assertEqual(user_roles.count(), 2, "Should still create both roles from token")

    #
    # def test_multiple_roles_with_notifications(self):
    #     """Test that appropriate notifications are sent for different roles."""
    #     # Set project status to trigger notifications
    #     self.project.status = ProjectStatus.REVIEW
    #     self.project.save()
    #
    #     # Add PROJECT_ADMIN role to trigger notification
    #     admin_invitation = {
    #         "email": self.new_user_email,
    #         "role": Role.PROJECT_ADMIN,
    #         "library_id": None,
    #     }
    #     self.invitations_data.append(admin_invitation)
    #     self.project.invitations.append(admin_invitation)
    #     self.project.save()
    #
    #     token_with_admin = self.signer.sign_object(
    #         {
    #             "email": self.new_user_email,
    #             "project_id": str(self.project.id),
    #             "invitations": self.invitations_data,  # Includes PROJECT_ADMIN
    #             "assigned_by_id": str(self.project_creator.id),
    #         }
    #     )
    #
    #     # Clear any existing emails
    #     mail.outbox = []
    #
    #     response = self.post(
    #         reverse("create_account"),
    #         {"token": token_with_admin, "password": "SecurePassword123!", "confirm_password": "SecurePassword123!"},
    #     )
    #
    #     self.response_created(response)
    #
    #     # Check that notification was sent (1 account creation + 1 admin review notification)
    #     self.assertEqual(len(mail.outbox), 2, "Should send account creation + admin review emails")
    #
    #     # Verify user has all 3 roles
    #     new_user = User.objects.get(email=self.new_user_email)
    #     user_roles = UserRole.objects.filter(user=new_user, project=self.project)
    #     self.assertEqual(user_roles.count(), 3, "Should have 3 roles: INSTRUCTOR, CONTROLLER, PROJECT_ADMIN")

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

    # class ProjectInvitationTests(TestCase):
    ...
    # def setUp(self):
    #     """
    #     Set up the test case.
    #     """
    #     super().setUp()
    #     with tenant_context(self.tenant):
    #         # Create admin and regular users
    #         self.admin = User.objects.create_user(username="admin", email="admin@eplouribousse.fr", is_active=True)
    #         self.regular_user = User.objects.create_user(
    #             username="regular", email="regular@eplouribouse.fr", is_active=True
    #         )
    #
    #         # Create project
    #         self.project = Project.objects.create(
    #             name="Test Project",
    #             description="Test Description",
    #             is_private=False,
    #         )
    #
    #         # Create library and associate with project
    #         self.library = Library.objects.create(name="Test Library")
    #         self.project.libraries.add(self.library)
    #
    #         # Assign admin role to admin user
    #         self.project.user_roles.create(user=self.admin, role=Role.PROJECT_ADMIN)
    #
    #         # Assign minimal role to regular user
    #         self.project.user_roles.create(user=self.regular_user, role=Role.GUEST)
    #
    # def test_add_invitation_success(self):
    #     """
    #     Test successfully adding an invitation to a project.
    #     """
    #     url = reverse("project-detail", kwargs={"pk": self.project.id}) + "invitations/"
    #     data = {
    #         "email": "newuser@example.com",
    #         "role": Role.GUEST,
    #     }
    #
    #     response = self.post(url, user=self.admin, data=data)
    #     self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    #
    #     with tenant_context(self.tenant):
    #         self.project.refresh_from_db()
    #         self.assertEqual(len(self.project.invitations), 1)
    #         self.assertEqual(self.project.invitations[0]["email"], "newuser@example.com")
    #         self.assertEqual(self.project.invitations[0]["role"], Role.GUEST)
    #
    # def test_add_invitation_instructor_with_library(self):
    #     """
    #     Test adding an instructor invitation with a valid library.
    #     """
    #     url = reverse("project-detail", kwargs={"pk": self.project.id}) + "invitations/"
    #     data = {
    #         "email": "instructor@example.com",
    #         "role": Role.INSTRUCTOR,
    #         "library": str(self.library.id),
    #     }
    #
    #     response = self.post(url, user=self.admin, data=data)
    #     self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    #
    #     with tenant_context(self.tenant):
    #         self.project.refresh_from_db()
    #         self.assertEqual(len(self.project.invitations), 1)
    #         self.assertEqual(self.project.invitations[0]["role"], Role.INSTRUCTOR)
    #         self.assertEqual(self.project.invitations[0]["library"], str(self.library.id))
    #
    # def test_add_invitation_instructor_without_library_fails(self):
    #     """
    #     Test that adding an instructor invitation without a library fails.
    #     """
    #     url = reverse("project-detail", kwargs={"pk": self.project.id}) + "invitations/"
    #     data = {
    #         "email": "instructor@example.com",
    #         "role": Role.INSTRUCTOR,
    #     }
    #
    #     response = self.post(url, user=self.admin, data=data)
    #     self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    #     self.assertIn("Library must be provided for instructor role", str(response.content))
    #
    # def test_add_invitation_with_invalid_library_fails(self):
    #     """
    #     Test that adding an invitation with an invalid library fails.
    #     """
    #     url = reverse("project-detail", kwargs={"pk": self.project.id}) + "invitations/"
    #     data = {
    #         "email": "instructor@example.com",
    #         "role": Role.INSTRUCTOR,
    #         "library": str(uuid.uuid4()),  # invalid library UUID
    #     }
    #
    #     response = self.post(url, user=self.admin, data=data)
    #     self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    #     self.assertIn("Library is not attached to the project", str(response.content))
    #
    # def test_add_duplicate_invitation_fails(self):
    #     """
    #     Test that adding a duplicate invitation fails.
    #     """
    #     url = reverse("project-detail", kwargs={"pk": self.project.id}) + "invitations/"
    #     data = {
    #         "email": "duplicate@example.com",
    #         "role": Role.GUEST,
    #     }
    #
    #     # First request should succeed
    #     response = self.post(url, user=self.admin, data=data)
    #     self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    #
    #     # Second request should fail
    #     response = self.post(url, user=self.admin, data=data)
    #     self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    #     self.assertIn("This invitation already exists", str(response.content))
    #
    # def test_remove_invitation_success(self):
    #     """
    #     Test successfully removing an invitation.
    #     """
    #     # First add an invitation
    #     add_url = reverse("project-detail", kwargs={"pk": self.project.id}) + "invitations/"
    #     data = {
    #         "email": "toremove@example.com",
    #         "role": Role.GUEST,
    #     }
    #     self.post(add_url, user=self.admin, data=data)
    #
    #     # Now remove it
    #     remove_url = reverse("project-detail", kwargs={"pk": self.project.id}) + "invitations/"
    #     response = self.delete(remove_url, user=self.admin, data=data)
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #
    #     with tenant_context(self.tenant):
    #         self.project.refresh_from_db()
    #         self.assertEqual(len(self.project.invitations), 0)
    #
    # def test_remove_nonexistent_invitation_fails(self):
    #     """
    #     Test that removing a non-existent invitation fails.
    #     """
    #     url = reverse("project-detail", kwargs={"pk": self.project.id}) + "invitations/"
    #     data = {
    #         "email": "nonexistent@example.com",
    #         "role": Role.GUEST,
    #     }
    #
    #     response = self.delete(url, user=self.admin, data=data)
    #     self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    #     self.assertIn("Invitation not found", str(response.content))
    #
    # def test_clear_invitations_success(self):
    #     """
    #     Test successfully clearing all invitations.
    #     """
    #     # First add some invitations
    #     url = reverse("project-detail", kwargs={"pk": self.project.id}) + "invitations/"
    #     data1 = {
    #         "email": "user1@example.com",
    #         "role": Role.GUEST,
    #     }
    #     data2 = {
    #         "email": "user2@example.com",
    #         "role": Role.CONTROLLER,
    #     }
    #     self.post(url, user=self.admin, data=data1)
    #     self.post(url, user=self.admin, data=data2)
    #
    #     # Now clear them
    #     clear_url = reverse("project-detail", kwargs={"pk": self.project.id}) + "invitations/clear/"
    #     response = self.delete(clear_url, user=self.admin)
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #
    #     with tenant_context(self.tenant):
    #         self.project.refresh_from_db()
    #         self.assertEqual(len(self.project.invitations), 0)
    #
    # def test_unauthenticated_access_fails(self):
    #     """
    #     Test that unauthenticated access to invitation endpoints fails.
    #     """
    #     url = reverse("project-detail", kwargs={"pk": self.project.id}) + "invitations/"
    #     data = {
    #         "email": "user@example.com",
    #         "role": Role.GUEST,
    #     }
    #
    #     # Test add invitation
    #     response = self.post(url, data=data)
    #     self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    #
    #     # Test remove invitation
    #     response = self.delete(url, data=data)
    #     self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    #
    #     # Test clear invitations
    #     clear_url = reverse("project-detail", kwargs={"pk": self.project.id}) + "invitations/clear/"
    #     response = self.delete(clear_url)
    #     self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    #
    # def test_unauthorized_access_fails(self):
    #     """
    #     Test that unauthorized access (regular user) to invitation endpoints fails.
    #     """
    #     url = reverse("project-detail", kwargs={"pk": self.project.id}) + "invitations/"
    #     data = {
    #         "email": "user@example.com",
    #         "role": Role.GUEST,
    #     }
    #
    #     # Test add invitation
    #     response = self.post(url, user=self.regular_user, data=data)
    #     self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    #
    #     # Test remove invitation
    #     response = self.delete(url, user=self.regular_user, data=data)
    #     self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    #
    #     # Test clear invitations
    #     clear_url = reverse("project-detail", kwargs={"pk": self.project.id}) + "invitations/clear/"
    #     response = self.delete(clear_url, user=self.regular_user)
    #     self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
