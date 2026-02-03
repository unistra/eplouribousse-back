from uuid import uuid4

from django.core import mail
from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context
from parameterized import parameterized

from epl.apps.project.models import ResourceStatus, Role, UserRole
from epl.apps.project.models.choices import AlertType
from epl.apps.project.models.collection import Arbitration
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.user import UserFactory, UserWithRoleFactory
from epl.apps.user.models import User
from epl.tests import TestCase


class BaseCollectionPositioningTest(TestCase):
    """Base class for collection positioning tests with common helper methods."""

    def setup_in_tenant_context(self, setup_func):
        with tenant_context(self.tenant):
            return setup_func()

    def create_library_with_instructor_and_collection(self, project, resource=None):
        library = LibraryFactory(project=project)
        instructor = UserWithRoleFactory(role=Role.INSTRUCTOR, project=project, library=library)
        collection = CollectionFactory(
            library=library,
            project=project,
            resource=resource if resource else ResourceFactory(project=project),
        )
        return library, instructor, collection

    def create_project_with_resource(self, resource_status=ResourceStatus.POSITIONING):
        project = ProjectFactory()
        resource = ResourceFactory(project=project)
        resource.status = resource_status
        resource.save()
        return project, resource

    def setup_multiple_libraries(self, project, resource, num_libraries=3):
        libraries_data = []
        for _ in range(num_libraries):
            library, instructor, collection = self.create_library_with_instructor_and_collection(project, resource)
            libraries_data.append((library, instructor, collection))
        return libraries_data


class CollectionPositionViewSetTest(BaseCollectionPositioningTest):
    def setUp(self):
        super().setUp()

        def _setup():
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

        self.setup_in_tenant_context(_setup)

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


class ResourceExclusionTest(BaseCollectionPositioningTest):
    def setUp(self):
        super().setUp()

        def _setup():
            self.project, self.resource = self.create_project_with_resource()

            libraries_data = self.setup_multiple_libraries(self.project, self.resource, num_libraries=3)
            for i, (library, instructor, collection) in enumerate(libraries_data, start=1):
                setattr(self, f"library_{i}", library)
                setattr(self, f"instructor_{i}", instructor)
                setattr(self, f"collection_{i}", collection)

        self.setup_in_tenant_context(_setup)

    def test_resource_status_change_to_excluded_after_last_library_excludes(self):
        """
        Tests that resource is excluded when:
        - first library positions its collection to rank 1
        - the following libraries exclude their collections
        """
        # Library 1 positions its collection to rank 1
        response = self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_1.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor_1,
        )
        self.response_ok(response)
        # Library 2 excludes its collection
        response = self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collection_2.id}),
            data={"exclusion_reason": "Participation in another project"},
            content_type="application/json",
            user=self.instructor_2,
        )
        self.response_ok(response)

        # resource.status is still POSITIONING
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.POSITIONING)

        # Library 3 excludes its collection
        response = self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collection_3.id}),
            data={"exclusion_reason": "Participation in another project"},
            content_type="application/json",
            user=self.instructor_3,
        )
        self.response_ok(response)

        # resource.status should now be EXCLUDED
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.EXCLUDED)

    def test_resource_status_change_to_excluded_after_positioning_2(self):
        """
        Tests that resource is excluded when:
        - first librairies exclude their collections
        - last librairy positions its collection to rank 1
        """

        # Library 2 excludes its collection
        response = self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collection_2.id}),
            data={"exclusion_reason": "Participation in another project"},
            content_type="application/json",
            user=self.instructor_2,
        )
        self.response_ok(response)

        # resource.status is still POSITIONING
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.POSITIONING)

        # Library 3 excludes its collection
        response = self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collection_3.id}),
            data={"exclusion_reason": "Participation in another project"},
            content_type="application/json",
            user=self.instructor_3,
        )
        self.response_ok(response)

        # Library 1 positions its collection to rank 1
        response = self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_1.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor_1,
        )
        self.response_ok(response)

        # resource.status should now be EXCLUDED
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.EXCLUDED)

    def test_resource_status_becomes_excluded_if_all_collections_are_excluded(self):
        """
        Tests that resource is excluded when all its collections are excluded.
        """
        # Library 1 excludes its collection
        self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collection_1.id}),
            data={"exclusion_reason": "Participation in another project"},
            content_type="application/json",
            user=self.instructor_1,
        )
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.POSITIONING)

        # Library 2 excludes its collection
        self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collection_2.id}),
            data={"exclusion_reason": "Participation in another project"},
            content_type="application/json",
            user=self.instructor_2,
        )
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.POSITIONING)

        # Library 3 excludes its collection (last one)
        self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collection_3.id}),
            data={"exclusion_reason": "Participation in another project"},
            content_type="application/json",
            user=self.instructor_3,
        )

        # resource.status should now be EXCLUDED
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.EXCLUDED)


class ArbitrationNotificationTest(BaseCollectionPositioningTest):
    def setUp(self):
        super().setUp()

        def _setup():
            self.project = ProjectFactory()
            self.resource = ResourceFactory(project=self.project)
            self.resource.arbitration = Arbitration.NONE
            self.resource.save()

            libraries_data = self.setup_multiple_libraries(self.project, self.resource, num_libraries=2)
            self.library_1, self.instructor_1, self.collection_1 = libraries_data[0]
            self.library_2, self.instructor_2, self.collection_2 = libraries_data[1]

            self.project.settings["alerts"][AlertType.ARBITRATION.value] = True
            self.project.save()

        self.setup_in_tenant_context(_setup)

    def test_arbitration_type_1_sends_notification_user_alerts_settings_by_default(self):
        """
        project.settings['alerts']['arbitration'] = True
        user.settings by default
        """
        # Set the collection_1 rank to 1
        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_1.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor_1,
        )
        self.collection_1.refresh_from_db()
        self.assertEqual(self.collection_1.position, 1)

        # Set the collection_2 rank to 1
        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_2.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor_2,
        )
        self.collection_2.refresh_from_db()
        self.resource.refresh_from_db()

        self.assertEqual(self.collection_2.position, 1)
        self.assertEqual(self.resource.arbitration, Arbitration.ONE)

        # 2 arbitration 0 emails should be sent, one to each instructor.
        expected_string_in_subject = "arbitration 1"
        arbitration_1_emails = [
            email for email in mail.outbox if expected_string_in_subject.lower() in str(email.subject).lower()
        ]

        expected_recipients = {self.instructor_1.email, self.instructor_2.email}
        actual_recipients = {email.to[0] for email in arbitration_1_emails}

        # check number of emails
        self.assertEqual(len(arbitration_1_emails), 2)

        # check recipient
        self.assertEqual(actual_recipients, expected_recipients)

        # check body
        expected_string_in_body = "The repositioning of your collection for the resource"
        for email in arbitration_1_emails:
            self.assertIn(expected_string_in_body, email.body)

        # check subject
        expected_subject_1 = f"eplouribousse | {self.tenant.name} | {self.project.name} | {self.library_1.code} | {self.resource.code} | arbitration {Arbitration.ONE.value}"
        expected_subject_2 = f"eplouribousse | {self.tenant.name} | {self.project.name} | {self.library_2.code} | {self.resource.code} | arbitration {Arbitration.ONE.value}"

        expected_subjects = {expected_subject_1, expected_subject_2}
        actual_subjects = {email.subject for email in arbitration_1_emails}
        self.assertEqual(actual_subjects, expected_subjects)

    def test_arbitration_type_1_sends_notification_user_alert_arbitration_true(self):
        # set the user alert arbitration to true
        self.instructor_1.settings.setdefault("alerts", {}).setdefault(str(self.project.id), {})[
            AlertType.ARBITRATION.value
        ] = False
        self.instructor_2.settings.setdefault("alerts", {}).setdefault(str(self.project.id), {})[
            AlertType.ARBITRATION.value
        ] = False
        # Set the collection_1 rank to 1
        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_1.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor_1,
        )
        self.collection_1.refresh_from_db()
        self.assertEqual(self.collection_1.position, 1)

        # Set the collection_2 rank to 1
        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_2.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor_2,
        )

        self.collection_2.refresh_from_db()
        self.resource.refresh_from_db()

        self.assertEqual(self.collection_2.position, 1)
        self.assertEqual(self.resource.arbitration, Arbitration.ONE)

        # 2 arbitration 1 emails should be sent, one to each instructor.
        expected_string_in_subject = "arbitration 1"
        arbitration_1_emails = [
            email for email in mail.outbox if expected_string_in_subject.lower() in str(email.subject).lower()
        ]

        expected_recipients = {self.instructor_1.email, self.instructor_2.email}
        actual_recipients = {email.to[0] for email in arbitration_1_emails}

        # check number of emails
        self.assertEqual(len(arbitration_1_emails), 2)

        # check recipient
        self.assertEqual(actual_recipients, expected_recipients)

        # check body
        expected_string_in_body = "The repositioning of your collection for the resource"
        for email in arbitration_1_emails:
            self.assertIn(expected_string_in_body, email.body)

        # check subject
        expected_subject_1 = f"eplouribousse | {self.tenant.name} | {self.project.name} | {self.library_1.code} | {self.resource.code} | arbitration {Arbitration.ONE.value}"
        expected_subject_2 = f"eplouribousse | {self.tenant.name} | {self.project.name} | {self.library_2.code} | {self.resource.code} | arbitration {Arbitration.ONE.value}"

        expected_subjects = {expected_subject_1, expected_subject_2}
        actual_subjects = {email.subject for email in arbitration_1_emails}
        self.assertEqual(actual_subjects, expected_subjects)

    def test_arbitration_type_1_does_not_send_notification_if_user_alert_arbitration_false(self):
        # set the user alert arbitration to false
        self.instructor_1.settings.setdefault("alerts", {}).setdefault(str(self.project.id), {})[
            AlertType.ARBITRATION.value
        ] = False
        self.instructor_1.save()
        self.instructor_1.refresh_from_db()
        self.instructor_2.settings.setdefault("alerts", {}).setdefault(str(self.project.id), {})[
            AlertType.ARBITRATION.value
        ] = False
        self.instructor_2.save()
        self.instructor_2.refresh_from_db()

        # Set the collection_1 rank to 1
        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_1.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor_1,
        )
        self.collection_1.refresh_from_db()
        self.assertEqual(self.collection_1.position, 1)

        # Set the collection_2 rank to 1
        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_2.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor_2,
        )

        self.collection_2.refresh_from_db()
        self.resource.refresh_from_db()

        self.assertEqual(self.collection_2.position, 1)
        self.assertEqual(self.resource.arbitration, Arbitration.ONE)

        # No arbitration 1 emails should be sent
        non_expected_subject_1 = f"eplouribousse | {self.tenant.name} | {self.project.name} | {self.library_1.code} | {self.resource.code} | arbitration {Arbitration.ONE.value}"
        non_expected_subject_2 = f"eplouribousse | {self.tenant.name} | {self.project.name} | {self.library_2.code} | {self.resource.code} | arbitration {Arbitration.ONE.value}"

        all_subjects = [email.subject for email in mail.outbox]

        self.assertNotIn(non_expected_subject_1, all_subjects)
        self.assertNotIn(non_expected_subject_2, all_subjects)

    def test_arbitration_type_0_sends_notification(self):
        # Set the collection_1 rank to 2
        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_1.id}),
            data={"position": 2},
            content_type="application/json",
            user=self.instructor_1,
        )

        # Set the collection_2 rank to 3
        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_2.id}),
            data={"position": 3},
            content_type="application/json",
            user=self.instructor_2,
        )

        self.collection_1.refresh_from_db()
        self.collection_2.refresh_from_db()
        self.resource.refresh_from_db()

        self.assertEqual(self.collection_1.position, 2)
        self.assertEqual(self.collection_2.position, 3)
        self.assertEqual(self.resource.arbitration, Arbitration.ZERO)

        # 2 arbitration 0 emails should be sent, one to each instructor.
        expected_string_in_subject = "arbitration 0"
        arbitration_0_emails = [
            email for email in mail.outbox if expected_string_in_subject.lower() in str(email.subject).lower()
        ]

        expected_recipients = {self.instructor_1.email, self.instructor_2.email}
        actual_recipients = {email.to[0] for email in arbitration_0_emails}

        # check number of emails
        self.assertEqual(len(arbitration_0_emails), 2)

        # check recipient
        self.assertEqual(actual_recipients, expected_recipients)

        # check body
        expected_string_in_body = "The repositioning of your collection for the resource"
        for email in arbitration_0_emails:
            self.assertIn(expected_string_in_body, email.body)

        # check subject
        expected_subject_1 = f"eplouribousse | {self.tenant.name} | {self.project.name} | {self.library_1.code} | {self.resource.code} | arbitration {Arbitration.ZERO.value}"
        expected_subject_2 = f"eplouribousse | {self.tenant.name} | {self.project.name} | {self.library_2.code} | {self.resource.code} | arbitration {Arbitration.ZERO.value}"

        expected_subjects = {expected_subject_1, expected_subject_2}
        actual_subjects = {email.subject for email in arbitration_0_emails}
        self.assertEqual(actual_subjects, expected_subjects)

    def test_arbitration_1_notifies_only_rank_1_instructors(self):
        """
        Only instructors of rank 1 collections should receive an email.
        """
        _library_3, instructor_3, collection_3 = self.setup_in_tenant_context(
            lambda: self.create_library_with_instructor_and_collection(self.project, self.resource)
        )

        self.patch(
            reverse("collection-position", kwargs={"pk": collection_3.id}),
            data={"position": 2},
            content_type="application/json",
            user=instructor_3,
        )
        collection_3.refresh_from_db()
        self.assertEqual(collection_3.position, 2)

        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_1.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor_1,
        )

        self.collection_1.refresh_from_db()
        self.assertEqual(self.collection_1.position, 1)

        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_2.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor_2,
        )
        self.collection_2.refresh_from_db()
        self.assertEqual(self.collection_1.position, 1)

        self.resource.refresh_from_db()

        self.assertEqual(self.resource.arbitration, Arbitration.ONE)

        # only instructor 1 and 3 should receive arbitration 1 email
        expected_string_in_subject = "arbitration 1"
        arbitration_1_emails = [
            email for email in mail.outbox if expected_string_in_subject.lower() in str(email.subject).lower()
        ]

        expected_recipients = {self.instructor_1.email, self.instructor_2.email}
        actual_recipients = {email.to[0] for email in arbitration_1_emails}

        self.assertEqual(len(arbitration_1_emails), 2)
        self.assertEqual(actual_recipients, expected_recipients)

    def test_arbitration_0_notifies_only_positioned_instructors(self):
        """
        Only instructors of non excluded collections should receive an email.
        """
        _library_3, instructor_3, collection_3 = self.setup_in_tenant_context(
            lambda: self.create_library_with_instructor_and_collection(self.project, self.resource)
        )

        # collection 1 and 2 are rank 2
        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_1.id}),
            data={"position": 2},
            content_type="application/json",
            user=self.instructor_1,
        )
        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_2.id}),
            data={"position": 2},
            content_type="application/json",
            user=self.instructor_2,
        )

        # collection 3 is excluded
        self.patch(
            reverse("collection-exclude", kwargs={"pk": collection_3.id}),
            data={"exclusion_reason": "Participation in another project"},
            content_type="application/json",
            user=instructor_3,
        )

        self.collection_1.refresh_from_db()
        self.collection_2.refresh_from_db()
        collection_3.refresh_from_db()
        self.resource.refresh_from_db()

        self.assertEqual(collection_3.exclusion_reason, "Participation in another project")

        self.assertEqual(self.resource.arbitration, Arbitration.ZERO)

        # Only instructor 1 and 2 should receive arbitration 0 email
        expected_string_in_subject = "arbitration 0"
        arbitration_0_emails = [
            email for email in mail.outbox if expected_string_in_subject.lower() in str(email.subject).lower()
        ]

        expected_recipients = {self.instructor_1.email, self.instructor_2.email}
        actual_recipients = {email.to[0] for email in arbitration_0_emails}

        self.assertEqual(len(arbitration_0_emails), 2)
        self.assertEqual(actual_recipients, expected_recipients)


class PositioningNotificationTest(BaseCollectionPositioningTest):
    def setUp(self):
        super().setUp()

        def _setup():
            self.project = ProjectFactory()
            self.resource = ResourceFactory(project=self.project)
            self.resource.arbitration = Arbitration.NONE
            self.resource.save()

            libraries_data = self.setup_multiple_libraries(self.project, self.resource, num_libraries=3)
            self.library_1, self.instructor_1, self.collection_1 = libraries_data[0]
            self.library_2, self.instructor_2, self.collection_2 = libraries_data[1]
            self.library_3, self.instructor_3, self.collection_3 = libraries_data[2]

            self.project.settings["alerts"][AlertType.POSITIONING.value] = True
            self.project.save()

        self.setup_in_tenant_context(_setup)

    def test_positioning_sends_notification(self):
        # Position the collection_1 to rank 2
        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_1.id}),
            data={"position": 2},
            content_type="application/json",
            user=self.instructor_1,
        )
        self.collection_1.refresh_from_db()
        self.assertEqual(self.collection_1.position, 2)

        # instructors 2 and 3 should receive an email
        self.assertEqual(len(mail.outbox), 2)
        expected_string_in_subject = "positioning"
        expected_recipients = [self.instructor_2.email, self.instructor_3.email]

        positioning_emails = [email for email in mail.outbox if expected_string_in_subject in str(email.subject)]
        self.assertEqual(len(positioning_emails), 2)

        actual_recipients = [email.to[0] for email in positioning_emails]
        self.assertEqual(sorted(actual_recipients), sorted(expected_recipients))

    def test_positioning_sends_notification_even_when_arbitration_1(self):
        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_1.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor_1,
        )
        mail.outbox = []
        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_2.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor_2,
        )
        self.collection_1.refresh_from_db()
        self.collection_2.refresh_from_db()

        self.assertEqual(self.collection_1.position, 1)
        self.assertEqual(self.collection_2.position, 1)
        self.assertEqual(self.collection_3.position, None)

        # only instructor_3 should receive a positioning email
        expected_recipients = [self.instructor_3.email]
        expected_string_in_subject = "positioning"
        positioning_emails = [email for email in mail.outbox if expected_string_in_subject in str(email.subject)]
        actual_recipients = [email.to[0] for email in positioning_emails]

        self.assertEqual(len(positioning_emails), 1)
        self.assertEqual(actual_recipients, expected_recipients)

    def test_no_email_sent_if_user_positioning_alert_disabled(self):
        # Deactivate the user alert positioning
        self.instructor_2.settings.setdefault("alerts", {}).setdefault(str(self.project.id), {})[
            AlertType.POSITIONING.value
        ] = False
        self.instructor_2.save()
        self.instructor_2.refresh_from_db()
        self.instructor_3.settings.setdefault("alerts", {}).setdefault(str(self.project.id), {})[
            AlertType.POSITIONING.value
        ] = False
        self.instructor_3.save()
        self.instructor_3.refresh_from_db()
        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_1.id}),
            data={"position": 2},
            content_type="application/json",
            user=self.instructor_1,
        )
        self.collection_1.refresh_from_db()
        self.assertEqual(self.collection_1.position, 2)
        self.assertEqual(len(mail.outbox), 0)


class ExcludedStatusTransitionTest(BaseCollectionPositioningTest):
    def setUp(self):
        super().setUp()

        def _setup():
            self.project, self.resource = self.create_project_with_resource()

            libraries_data = self.setup_multiple_libraries(self.project, self.resource, num_libraries=2)
            self.library_a, self.instructor_a, self.collection_a = libraries_data[0]
            self.library_b, self.instructor_b, self.collection_b = libraries_data[1]

        self.setup_in_tenant_context(_setup)

    def test_excluded_status_cleared_when_collection_repositioned_from_exclusion(self):
        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_a.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor_a,
        )

        self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collection_b.id}),
            data={"exclusion_reason": "Participation in another project"},
            content_type="application/json",
            user=self.instructor_b,
        )

        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.EXCLUDED)

        response = self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_b.id}),
            data={"position": 2},
            content_type="application/json",
            user=self.instructor_b,
        )
        self.response_ok(response)

        self.resource.refresh_from_db()
        self.assertNotEqual(
            self.resource.status,
            ResourceStatus.EXCLUDED,
            "Resource should no longer be EXCLUDED after lib B repositions from exclusion",
        )
        self.assertEqual(
            self.resource.status,
            ResourceStatus.INSTRUCTION_BOUND,
            "Resource should move to INSTRUCTION_BOUND when all positioned and no arbitration needed",
        )

    def test_excluded_status_cleared_when_collection_repositioned_to_rank_1(self):
        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_a.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor_a,
        )

        self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collection_b.id}),
            data={"exclusion_reason": "Participation in another project"},
            content_type="application/json",
            user=self.instructor_b,
        )

        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.EXCLUDED)

        response = self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_b.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor_b,
        )
        self.response_ok(response)

        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.POSITIONING)
        self.assertEqual(self.resource.arbitration, Arbitration.ONE)

    def test_excluded_status_maintained_when_conditions_still_met(self):
        _library_c, instructor_c, collection_c = self.setup_in_tenant_context(
            lambda: self.create_library_with_instructor_and_collection(self.project, self.resource)
        )

        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_a.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor_a,
        )

        self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collection_b.id}),
            data={"exclusion_reason": "Participation in another project"},
            content_type="application/json",
            user=self.instructor_b,
        )

        self.patch(
            reverse("collection-exclude", kwargs={"pk": collection_c.id}),
            data={"exclusion_reason": "Participation in another project"},
            content_type="application/json",
            user=instructor_c,
        )

        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.EXCLUDED)

        self.patch(
            reverse("collection-exclude", kwargs={"pk": collection_c.id}),
            data={"exclusion_reason": "Other reason"},
            content_type="application/json",
            user=instructor_c,
        )

        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.EXCLUDED)

    def test_excluded_status_cleared_when_rank_1_collection_changes_position(self):
        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_a.id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructor_a,
        )

        self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collection_b.id}),
            data={"exclusion_reason": "Participation in another project"},
            content_type="application/json",
            user=self.instructor_b,
        )

        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.EXCLUDED)

        response = self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_a.id}),
            data={"position": 2},
            content_type="application/json",
            user=self.instructor_a,
        )
        self.response_ok(response)

        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.POSITIONING)
        self.assertEqual(self.resource.arbitration, Arbitration.ZERO)


class PositionSerializerEdgeCasesTest(BaseCollectionPositioningTest):
    def setUp(self):
        super().setUp()

        def _setup():
            self.project = ProjectFactory()
            self.resource = ResourceFactory(project=self.project)

            libraries_data = self.setup_multiple_libraries(self.project, self.resource, num_libraries=3)

            self.libraries = [lib for lib, _, _ in libraries_data]
            self.instructors = [instr for _, instr, _ in libraries_data]
            self.collections = [coll for _, _, coll in libraries_data]

        self.setup_in_tenant_context(_setup)

    def test_multiple_repositioning_preserves_correct_state(self):
        for i, collection in enumerate(self.collections):
            self.patch(
                reverse("collection-position", kwargs={"pk": collection.id}),
                data={"position": 2},
                content_type="application/json",
                user=self.instructors[i],
            )

        self.resource.refresh_from_db()
        self.assertEqual(self.resource.arbitration, Arbitration.ZERO)
        self.assertEqual(self.resource.status, ResourceStatus.POSITIONING)

        self.patch(
            reverse("collection-position", kwargs={"pk": self.collections[0].id}),
            data={"position": 1},
            content_type="application/json",
            user=self.instructors[0],
        )

        self.resource.refresh_from_db()
        self.assertEqual(self.resource.arbitration, Arbitration.NONE)
        self.assertEqual(self.resource.status, ResourceStatus.INSTRUCTION_BOUND)

    def test_repositioning_clears_exclusion_reason(self):
        self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collections[0].id}),
            data={"exclusion_reason": "Participation in another project"},
            content_type="application/json",
            user=self.instructors[0],
        )

        self.collections[0].refresh_from_db()
        self.assertEqual(self.collections[0].exclusion_reason, "Participation in another project")

        response = self.patch(
            reverse("collection-position", kwargs={"pk": self.collections[0].id}),
            data={"position": 2},
            content_type="application/json",
            user=self.instructors[0],
        )
        self.response_ok(response)

        self.collections[0].refresh_from_db()
        self.assertEqual(self.collections[0].exclusion_reason, "")
        self.assertEqual(self.collections[0].position, 2)
