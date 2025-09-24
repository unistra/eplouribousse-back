from django.core import mail
from django_tenants.urlresolvers import reverse
from parameterized import parameterized

from epl.apps.project.models import ResourceStatus, Role
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class FinishInstructionTurnTest(TestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory()
        self.library = LibraryFactory()
        self.instructor = UserWithRoleFactory(
            role=Role.INSTRUCTOR,
            project=self.project,
            library=self.library,
        )
        self.resource = ResourceFactory(project=self.project)
        self.collection = CollectionFactory(resource=self.resource, library=self.library, project=self.project)

    def test_anonymous_access_is_not_allowed(self):
        collection = CollectionFactory()
        response = self.post(reverse("collection-finish-instruction-turn", kwargs={"pk": collection.id}))
        self.response_unauthorized(response)

    @parameterized.expand(
        [
            ResourceStatus.POSITIONING,
            ResourceStatus.CONTROL_BOUND,
            ResourceStatus.CONTROL_UNBOUND,
        ]
    )
    def test_resource_must_be_in_instruction_bound_or_unbound_status(self, status):
        self.resource.status = status
        self.resource.instruction_turns = {
            "bound_copies": {
                "turns": [
                    {
                        "library": str(self.library.id),
                        "collection": str(self.collection.id),
                    }
                ]
            },
            "unbound_copies": {
                "turns": [
                    {
                        "library": str(self.library.id),
                        "collection": str(self.collection.id),
                    }
                ]
            },
        }
        self.resource.save()
        response = self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection.id}),
            user=self.instructor,
        )
        self.response_bad_request(response)

    def test_only_instructor_of_the_project_and_library_can_finish_instruction_turn(self):
        self.resource.status = ResourceStatus.INSTRUCTION_BOUND
        self.resource.instruction_turns = {
            "bound_copies": {
                "turns": [
                    {
                        "library": str(self.library.id),
                        "collection": str(self.collection.id),
                    }
                ]
            },
            "unbound_copies": {"turns": []},
        }
        self.resource.save()
        admin = UserWithRoleFactory(role=Role.PROJECT_ADMIN, project=self.project)
        response = self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection.id}),
            user=admin,
        )
        self.response_forbidden(response)

    def test_if_no_instruction_turns_are_left_the_turn_can_not_be_finished(self):
        self.resource.status = ResourceStatus.INSTRUCTION_BOUND
        self.resource.instruction_turns = {
            "bound_copies": {"turns": []},
            "unbound_copies": {"turns": []},
        }
        self.resource.save()
        response = self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection.id}),
            user=self.instructor,
        )
        self.response_bad_request(response)
        self.assertIn("Invalid turn data", str(response.data[0]))

    def test_invalid_instruction_turn_data_can_not_be_finished(self):
        self.resource.status = ResourceStatus.INSTRUCTION_BOUND
        self.resource.instruction_turns = {
            "bound_copies": {"turns": ""},
            "unbound_copies": {"turns": []},
        }
        self.resource.save()
        response = self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection.id}),
            user=self.instructor,
        )
        self.response_bad_request(response)
        self.assertIn("Invalid turn data", str(response.data[0]))

    def test_turn_must_match_library_and_collection(self):
        other_library = LibraryFactory()
        other_collection = CollectionFactory(resource=self.resource, library=other_library, project=self.project)
        self.resource.status = ResourceStatus.INSTRUCTION_BOUND
        self.resource.instruction_turns = {
            "bound_copies": {
                "turns": [
                    {
                        "library": str(other_library.id),
                        "collection": str(other_collection.id),
                    }
                ]
            },
            "unbound_copies": {"turns": []},
        }
        self.resource.save()
        response = self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection.id}),
            user=self.instructor,
        )
        self.response_forbidden(response)

    def test_finish_turn_and_move_to_control(self):
        self.resource.status = ResourceStatus.INSTRUCTION_BOUND
        self.resource.instruction_turns = {
            "bound_copies": {
                "turns": [
                    {
                        "library": str(self.library.id),
                        "collection": str(self.collection.id),
                    }
                ]
            },
            "unbound_copies": {
                "turns": [
                    {
                        "library": str(self.library.id),
                        "collection": str(self.collection.id),
                    }
                ]
            },
        }
        self.resource.save()
        response = self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection.id}),
            user=self.instructor,
        )
        self.response_ok(response)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.CONTROL_BOUND)
        self.assertEqual(
            self.resource.instruction_turns,
            {
                "bound_copies": {"turns": []},
                "unbound_copies": {
                    "turns": [
                        {
                            "library": str(self.library.id),
                            "collection": str(self.collection.id),
                        }
                    ]
                },
            },
        )


class SendNotificationToInstruct(TestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory()
        self.library_1 = LibraryFactory()
        self.instructor_1 = UserWithRoleFactory(
            role=Role.INSTRUCTOR,
            project=self.project,
            library=self.library_1,
        )
        self.resource = ResourceFactory(project=self.project)
        self.collection_1 = CollectionFactory(resource=self.resource, library=self.library_1, project=self.project)

        self.library_2 = LibraryFactory()
        self.instructor_2 = UserWithRoleFactory(
            role=Role.INSTRUCTOR,
            project=self.project,
            library=self.library_2,
        )
        self.collection_2 = CollectionFactory(resource=self.resource, library=self.library_2, project=self.project)

    def test_send_notification_to_instruct(self):
        self.collection_1.position = 1
        self.collection_1.save()

        self.patch(
            reverse("collection-position", kwargs={"pk": self.collection_2.id}),
            data={"position": 2},
            content_type="application/json",
            user=self.instructor_2,
        )

        self.collection_2.refresh_from_db()
        self.resource.refresh_from_db()

        # instructor_1 should receive an invitation to instruct
        expected_recipients = [self.instructor_1.email]
        expected_string_in_subject = "instruction"
        instruction_emails = [email for email in mail.outbox if expected_string_in_subject in str(email.subject)]
        actual_recipients = [email.to[0] for email in instruction_emails]

        self.assertEqual(len(instruction_emails), 1)
        self.assertEqual(actual_recipients, expected_recipients)
        mail.outbox = []

        # instructor 1 finishes his turn
        self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection_1.id}),
            content_type="application/json",
            user=self.instructor_1,
        )
        self.resource.refresh_from_db()
        self.assertNotIn(self.collection_1.id, self.resource.instruction_turns["bound_copies"]["turns"])

        # instructor_2 should receive an invitation to instruct
        expected_recipients = [self.instructor_2.email]
        expected_string_in_subject = "instruction"
        instruction_emails = [email for email in mail.outbox if expected_string_in_subject in str(email.subject)]
        actual_recipients = [email.to[0] for email in instruction_emails]

        self.assertEqual(len(instruction_emails), 1)
        self.assertEqual(actual_recipients, expected_recipients)

    def test_no_instruction_notification_for_excluded_collection(self):
        """
        Check that no notification is sent to instructors for excluded collections.
        """
        library_3 = LibraryFactory()
        instructor_3 = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=library_3)
        collection_3 = CollectionFactory(resource=self.resource, library=library_3, project=self.project)

        # Instructor 1 positions its collection in position 1.
        self.collection_1.position = 1
        self.collection_1.save()

        # Instructor 2 excludes its collection.
        self.patch(
            reverse("collection-exclude", kwargs={"pk": self.collection_2.id}),
            data={"exclusion_reason": "Other"},
            content_type="application/json",
            user=self.instructor_2,
        )
        self.collection_2.refresh_from_db()
        self.assertTrue(self.collection_2.is_excluded)

        mail.outbox = []

        # Instructor 3 positions its collection in position 2.
        # This should trigger instruction
        self.patch(
            reverse("collection-position", kwargs={"pk": collection_3.id}),
            data={"position": 2},
            content_type="application/json",
            user=instructor_3,
        )
        self.resource.refresh_from_db()

        self.assertEqual(self.resource.status, ResourceStatus.INSTRUCTION_BOUND)

        # Turns list should contain 2 collections (1 and 3)
        turns = self.resource.instruction_turns["bound_copies"]["turns"]
        self.assertEqual(len(turns), 2)
        turn_collection_ids = [turn["collection"] for turn in turns]
        self.assertNotIn(str(self.collection_2.id), turn_collection_ids)

        # Check turns order: 1 then 3
        self.assertEqual(turn_collection_ids[0], str(self.collection_1.id))
        self.assertEqual(turn_collection_ids[1], str(collection_3.id))

        # Only 1 email should be sent: the one for instructor 1.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.instructor_1.email])

        mail.outbox = []

        # instructor 1 finishes his turn
        self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection_1.id}),
            content_type="application/json",
            user=self.instructor_1,
        )

        # Only 1 email should be sent: the one for instructor 3.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [instructor_3.email])
