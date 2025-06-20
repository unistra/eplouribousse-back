from epl.tests import TestCase


class ProjectInvitationTests(TestCase):
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
