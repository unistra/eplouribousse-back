from uuid import uuid4

from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context

from epl.apps.project.models import Collection, Library, Project, Role, UserRole
from epl.apps.user.models import User
from epl.tests import TestCase


class CollectionPositionViewSetTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.user = User.objects.create_user(email="test_user@eplouribousse.fr")
            self.project = Project.objects.create(name="test_project", description="Test project for collections")
            self.library = Library.objects.create(name="test_library", alias="TL", code="12345")

        self.collection = Collection.objects.create(
            title="Test Collection", code="TEST001", library=self.library, project=self.project, created_by=self.user
        )

        UserRole.objects.create(
            user=self.user, project=self.project, library=self.library, role=Role.INSTRUCTOR, assigned_by=self.user
        )

    # Positioning a collection - tests / PATCH /api/collections/{id}/position/
    def test_position_collection_success(self):
        data = {"position": 1}
        response = self.patch(
            reverse("collection-position", kwargs={"pk": self.collection.id}),
            data=data,
            content_type="application/json",
            user=self.user,
        )
        self.response_ok(response)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.position, 1)

    def test_position_collection_invalid_position(self):
        data = {"position": 0}
        response = self.patch(
            reverse("collection-position", kwargs={"pk": self.collection.id}),
            data=data,
            content_type="application/json",
            user=self.user,
        )
        self.response_bad_request(response)
        self.assertIn("position", response.data)
        print(response.data)

    def test_position_collection_requires_authentication(self):
        data = {"position": 1}
        response = self.patch(
            reverse("collection-position", kwargs={"pk": self.collection.id}),
            data=data,
            content_type="application/json",
        )  # no user provided = unauthenticated request
        self.response_unauthorized(response)  # 401 Unauthorized

    def test_position_requires_instructor_role(self):
        another_user = User.objects.create_user(email="another_user@eplouribousse.fr")
        UserRole.objects.create(
            user=another_user, project=self.project, library=self.library, role=Role.GUEST, assigned_by=self.user
        )
        data = {"position": 1}
        response = self.patch(
            reverse("collection-position", kwargs={"pk": self.collection.id}),
            data=data,
            content_type="application/json",
            user=another_user,
        )

        self.response_forbidden(response)

    # Add a comment to the collection - tests / PATCH /api/collections/{id}/comment-positioning/

    def test_add_comment_positioning_success(self):
        data = {"positioning_comment": "This is my beautiful comment for positioning."}
        response = self.patch(
            reverse("collection-comment-positioning", kwargs={"pk": self.collection.id}),
            data=data,
            content_type="application/json",
            user=self.user,
        )
        self.response_ok(response)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.positioning_comment, "This is my beautiful comment for positioning.")

    def test_update_comment_positioning_success(self):
        self.collection.positioning_comment = "This is my initial beautiful comment for positioning."
        self.collection.save()

        data = {"positioning_comment": "This is my updated but still beautiful comment for positioning."}
        response = self.patch(
            reverse("collection-comment-positioning", kwargs={"pk": self.collection.id}),
            data=data,
            content_type="application/json",
            user=self.user,
        )
        print(response)
        self.response_ok(response)
        self.collection.refresh_from_db()
        self.assertEqual(
            self.collection.positioning_comment, "This is my updated but still beautiful comment for positioning."
        )

    def test_positioning_comment_requires_authentication(self):
        data = {"positioning_comment": "Test comment"}
        response = self.patch(
            reverse("collection-comment-positioning", kwargs={"pk": self.collection.id}), data=data, user=None
        )
        self.response_unauthorized(response)

    def test_positioning_comment_requires_instructor_role(self):
        another_user = User.objects.create_user(email="another_user@eplouribousse.fr")
        data = {"positioning_comment": "Test comment"}
        response = self.patch(
            reverse("collection-comment-positioning", kwargs={"pk": self.collection.id}), data=data, user=another_user
        )
        self.response_forbidden(response)

    def test_positioning_comment_collection_not_found(self):
        data = {"positioning_comment": "Test comment for unexisting collection"}
        response = self.patch(
            reverse("collection-comment-positioning", kwargs={"pk": uuid4()}), data=data, user=self.user
        )
        self.response_not_found(response)

    # Exclude a collection - tests / PATCH /api/collections/{id}/exclude/

    def test_exclude_collection_with_exclusion_reason(self):
        data = {"exclusion_reason": "Participation in another project"}
        response = self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collection.id}),
            data=data,
            content_type="application/json",
            user=self.user,
        )
        self.response_ok(response)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.exclusion_reason, "Participation in another project")

    def test_exclude_collection_requires_authentication(self):
        data = {"exclusion_reason": "Participation in another project"}
        response = self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collection.id}),
            data=data,
            content_type="application/json",
            user=None,
        )
        self.response_unauthorized(response)

    def test_exclude_collection_requires_instructor_role(self):
        regular_user = User.objects.create_user(email="regular@eplouribousse.fr")
        data = {"exclusion_reason": "Participation in another project"}
        response = self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collection.id}),
            data=data,
            content_type="application/json",
            user=regular_user,
        )
        self.response_forbidden(response)

    # test exclure collection puis positionner supprime les motifs d'exclusion.

    def test_position_excluded_collection_clears_exclusion_reason(self):
        # Exclude the collection first
        exclude_data = {"exclusion_reason": "Participation in another project"}
        self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collection.id}),
            data=exclude_data,
            content_type="application/json",
            user=self.user,
        )

        # Now position the collection
        position_data = {"position": 1}
        response = self.patch(
            reverse("collection-position", kwargs={"pk": self.collection.id}),
            data=position_data,
            content_type="application/json",
            user=self.user,
        )
        self.response_ok(response)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.exclusion_reason, "")
