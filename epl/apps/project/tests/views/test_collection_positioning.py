from uuid import uuid4

from django.core import mail
from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context
from parameterized import parameterized

from epl.apps.project.models import ResourceStatus, Role, UserRole
from epl.apps.project.models.collection import Arbitration
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.user import UserFactory, UserWithRoleFactory
from epl.apps.user.models import User
from epl.tests import TestCase


class CollectionPositionViewSetTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.instructor = UserFactory()
            self.project = ProjectFactory()
            self.library = LibraryFactory()

            self.collection = CollectionFactory(library=self.library, project=self.project, created_by=self.instructor)

            UserRole.objects.create(
                user=self.instructor,
                project=self.project,
                library=self.library,
                role=Role.INSTRUCTOR,
                assigned_by=self.instructor,
            )

    # Positioning a collection - tests / PATCH /api/collections/{id}/position/

    @parameterized.expand(
        [
            (Role.PROJECT_CREATOR, False, 403),
            (Role.INSTRUCTOR, True, 200),
            (Role.PROJECT_ADMIN, False, 403),
            (Role.PROJECT_MANAGER, False, 403),
            (Role.CONTROLLER, False, 403),
            (Role.GUEST, False, 403),
            (None, False, 403),
        ]
    )
    def test_position_collection_permissions(self, role, should_succeed, expected_status):
        user = UserWithRoleFactory(role=role, project=self.project, library=self.library)
        data = {"position": 1}
        response = self.patch(
            reverse("collection-position", kwargs={"pk": self.collection.id}),
            data=data,
            content_type="application/json",
            user=user,
        )
        self.assertEqual(response.status_code, expected_status)

        self.collection.refresh_from_db()
        if should_succeed:
            self.assertEqual(self.collection.position, 1)
        else:
            self.assertEqual(self.collection.position, None)

    def test_position_collection_invalid_position(self):
        data = {"position": 0}
        response = self.patch(
            reverse("collection-position", kwargs={"pk": self.collection.id}),
            data=data,
            content_type="application/json",
            user=self.instructor,
        )
        self.response_bad_request(response)
        self.assertIn("position", response.data)

    # Add a comment to the collection - tests / PATCH /api/collections/{id}/comment-positioning/

    def test_add_comment_positioning_success(self):
        data = {"content": "This is my beautiful comment for positioning."}
        response = self.patch(
            reverse("collection-comment-positioning", kwargs={"pk": self.collection.id}),
            data=data,
            content_type="application/json",
            user=self.instructor,
        )
        self.response_ok(response)
        self.collection.refresh_from_db()
        self.assertEqual(
            self.collection.comments.filter(subject="Positioning comment").first().content,
            "This is my beautiful comment for positioning.",
        )

    def test_positioning_comment_requires_authentication(self):
        data = {"content": "Test comment"}
        response = self.patch(
            reverse("collection-comment-positioning", kwargs={"pk": self.collection.id}), data=data, user=None
        )
        self.response_unauthorized(response)

    def test_positioning_comment_requires_instructor_role(self):
        another_user = User.objects.create_user(email="another_user@eplouribousse.fr")
        data = {"content": "Test comment"}
        response = self.patch(
            reverse("collection-comment-positioning", kwargs={"pk": self.collection.id}),
            data=data,
            user=another_user,
            content_type="application/json",
        )
        self.response_forbidden(response)

    def test_positioning_comment_collection_not_found(self):
        data = {"content": "Test comment for unexisting collection"}
        response = self.patch(
            reverse("collection-comment-positioning", kwargs={"pk": uuid4()}),
            data=data,
            user=self.instructor,
            content_type="application/json",
        )
        self.response_not_found(response)

    # Exclude a collection - tests / PATCH /api/collections/{id}/exclude/
    @parameterized.expand(
        [
            (Role.PROJECT_CREATOR, False, 403),
            (Role.INSTRUCTOR, True, 200),
            (Role.PROJECT_ADMIN, False, 403),
            (Role.PROJECT_MANAGER, False, 403),
            (Role.CONTROLLER, False, 403),
            (Role.GUEST, False, 403),
            (None, False, 403),
        ]
    )
    def test_exclude_collection_permissions(self, role, should_succeed, expected_status):
        user = UserWithRoleFactory(role=role, project=self.project, library=self.library)
        data = {"exclusion_reason": "Participation in another project"}
        response = self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collection.id}),
            data=data,
            content_type="application/json",
            user=user,
        )
        self.assertEqual(response.status_code, expected_status)

        self.collection.refresh_from_db()
        if should_succeed:
            self.assertEqual(self.collection.exclusion_reason, "Participation in another project")
        else:
            self.assertEqual(self.collection.exclusion_reason, "")

    # test exclure collection puis positionner supprime les motifs d'exclusion.
    def test_position_excluded_collection_clears_exclusion_reason(self):
        # Exclude the collection first
        exclude_data = {"exclusion_reason": "Participation in another project"}
        self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collection.id}),
            data=exclude_data,
            content_type="application/json",
            user=self.instructor,
        )

        # Now position the collection
        position_data = {"position": 1}
        response = self.patch(
            reverse("collection-position", kwargs={"pk": self.collection.id}),
            data=position_data,
            content_type="application/json",
            user=self.instructor,
        )
        self.response_ok(response)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.exclusion_reason, "")

    def test_last_user_to_position_makes_the_collection_change_status(self):
        resource = self.collection.resource
        self.assertEqual(resource.status, ResourceStatus.POSITIONING)

        new_collection = CollectionFactory(
            library=self.library, project=self.project, created_by=self.instructor, resource=resource
        )

        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection.id}),
            data={"position": 3},
            content_type="application/json",
            user=self.instructor,
        )

        self.patch(
            reverse("collection-position", kwargs={"pk": new_collection.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor,
        )

        resource.refresh_from_db()

        self.assertEqual(resource.status, ResourceStatus.INSTRUCTION_BOUND)

    def test_arbitration_type_0(self):
        resource = self.collection.resource
        self.assertEqual(resource.arbitration, Arbitration.NONE)

        new_collection = CollectionFactory(
            library=self.library, project=self.project, created_by=self.instructor, resource=resource
        )

        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection.id}),
            data={"position": 2},
            content_type="application/json",
            user=self.instructor,
        )

        self.patch(
            reverse("collection-position", kwargs={"pk": new_collection.id}),
            data={"position": 2},
            content_type="application/json",
            user=self.instructor,
        )

        resource.refresh_from_db()
        self.assertEqual(resource.arbitration, Arbitration.ZERO)
        self.assertEqual(resource.status, ResourceStatus.POSITIONING)

    def test_arbitration_type_1(self):
        resource = self.collection.resource
        self.assertEqual(resource.arbitration, Arbitration.NONE)

        new_collection = CollectionFactory(
            library=self.library, project=self.project, created_by=self.instructor, resource=resource
        )

        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor,
        )

        self.patch(
            reverse("collection-position", kwargs={"pk": new_collection.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor,
        )

        resource.refresh_from_db()
        self.assertEqual(resource.arbitration, Arbitration.ONE)
        self.assertEqual(resource.status, ResourceStatus.POSITIONING)


class ArbitrationNotificationTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.project = ProjectFactory()
            self.resource = ResourceFactory(project=self.project)

            self.library_1 = LibraryFactory(project=self.project)
            self.instructor_1 = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library_1)
            self.collection_1 = CollectionFactory(library=self.library_1, project=self.project, resource=self.resource)

            self.library_2 = LibraryFactory(project=self.project)
            self.instructor_2 = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library_2)
            self.collection_2 = CollectionFactory(library=self.library_2, project=self.project, resource=self.resource)

    def test_arbitration_type_1_sends_notification(self):
        self.resource.arbitration = Arbitration.ONE

        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_2.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor_2,
        )

        self.collection_2.refresh_from_db()

        self.assertEqual(self.collection_2.position, 1)
        self.assertEqual(self.resource.arbitration, Arbitration.ONE)
        self.assertEqual(len(mail.outbox), 1)


class ArbitrationNotificationTestDRAFT(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.project = ProjectFactory()
            self.resource = ResourceFactory(project=self.project)

            self.library_1 = LibraryFactory(project=self.project)
            self.instructor_1 = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library_1)
            self.collection_1 = CollectionFactory(library=self.library_1, project=self.project, resource=self.resource)

            self.library_2 = LibraryFactory(project=self.project)
            self.instructor_2 = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library_2)
            self.collection_2 = CollectionFactory(library=self.library_2, project=self.project, resource=self.resource)

    def test_arbitration_type_1_sends_notification(self):
        self.collection_1.arbitration = Arbitration.ONE


def test_sends_email_on_type1_arbitration(self):
    """
    Vérifie que l'email est envoyé aux bons instructeurs lors d'un arbitrage de type 1.
    """
    # Set the collection rank to 1
    self.patch(
        reverse("collection-position", kwargs={"pk": self.collection.id}),
        data={"position": 1},
        content_type="application/json",
        user=self.instructor,
    )
    self.collection.refresh_from_db()

    # verify collection rank is 1
    self.assertEqual(self.collection.position, 1)

    # verify that no email is sent yet
    self.assertEqual(len(mail.outbox), 0)

    # GIVEN: Un deuxième instructeur et une deuxième collection sur la même ressource
    library2 = LibraryFactory(project=self.project)
    instructor2 = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=library2)
    collection2 = CollectionFactory(resource=self.collection.resource, library=library2, project=self.project)

    response = self.patch(
        reverse("collection-position", kwargs={"pk": collection2.id}),
        data={"position": 1},
        content_type="application/json",
        user=instructor2,
    )
    self.response_ok(response)
    self.collection.refresh_from_db()
    self.assertEqual(self.collection.resource.arbitration, Arbitration.ONE)
    print(len(mail.outbox))

    self.assertEqual(len(mail.outbox), 1)
