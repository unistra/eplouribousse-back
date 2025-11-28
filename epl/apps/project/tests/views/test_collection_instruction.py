from django.core import mail
from django_tenants.urlresolvers import reverse
from parameterized import parameterized

from epl.apps.project.models import ResourceStatus, Role
from epl.apps.project.models.choices import AlertType
from epl.apps.project.models.segment import CONTENT_NIHIL
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.segment import SegmentFactory
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

    def test_finish_turn_without_creating_segments_adds_nihil_segment(self):
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
        initial_segment_count = self.collection.segments.count()
        response = self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection.id}),
            user=self.instructor,
        )
        self.response_ok(response)
        self.collection.refresh_from_db()
        final_segment_count = self.collection.segments.count()
        self.assertEqual(final_segment_count, initial_segment_count + 1)
        nihil_segment = self.collection.segments.get(order=final_segment_count)
        self.assertEqual(nihil_segment.content, CONTENT_NIHIL)

    def test_if_segments_exist_nihil_segment_is_inserted_before(self):
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
        # Create an initial segment
        other_library = LibraryFactory()
        self.project.libraries.add(other_library)
        other_collection = CollectionFactory(resource=self.resource, library=self.library, project=self.project)
        _segment = SegmentFactory(order=1, collection=other_collection, content="Initial segment")

        response = self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection.id}),
            user=self.instructor,
        )
        self.response_ok(response)
        self.collection.refresh_from_db()
        segments = self.collection.resource.segments.order_by("order")
        self.assertEqual(segments.count(), 2)
        self.assertEqual(segments[0].content, CONTENT_NIHIL)
        self.assertEqual(segments[0].order, 1)
        self.assertEqual(segments[1].content, "Initial segment")
        self.assertEqual(segments[1].order, 2)


class SendNotificationToInstruct(TestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory()
        self.project.settings["alerts"][AlertType.INSTRUCTION.value] = True
        self.project.save()

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

    def test_no_instruction_notification_if_user_alert_false(self):
        # Deactivate instruction alerts for instructor_1
        self.instructor_1.settings.setdefault("alerts", {}).setdefault(str(self.project.id), {})[
            AlertType.INSTRUCTION.value
        ] = False
        self.instructor_1.save()
        self.instructor_1.refresh_from_db()

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

        # Check that no email was sent to instructor_1
        expected_string_in_subject = "instruction"
        instruction_emails = [email for email in mail.outbox if expected_string_in_subject in str(email.subject)]
        actual_recipients = [email.to[0] for email in instruction_emails]

        self.assertNotIn(self.instructor_1.email, actual_recipients)
        self.assertEqual(len(instruction_emails), 0)


class ControlPhaseTest(TestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory()
        self.project.settings["alerts"][AlertType.CONTROL.value] = True
        self.project.settings["alerts"][AlertType.INSTRUCTION.value] = True
        self.project.save()

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

        self.controller = UserWithRoleFactory(
            role=Role.CONTROLLER,
            project=self.project,
        )

    def test_send_notifications_to_control(self):
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

        # instructor 1 finishes his turn
        self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection_1.id}),
            content_type="application/json",
            user=self.instructor_1,
        )
        self.resource.refresh_from_db()
        self.assertNotIn(self.collection_1.id, self.resource.instruction_turns["bound_copies"]["turns"])

        mail.outbox = []

        # instructor 2 finishes his turn
        self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection_2.id}),
            content_type="application/json",
            user=self.instructor_2,
        )
        self.resource.refresh_from_db()
        self.assertNotIn(self.collection_2.id, self.resource.instruction_turns["bound_copies"]["turns"])

        # This should trigger control phase
        # The controller is notified
        self.assertEqual(self.resource.status, ResourceStatus.CONTROL_BOUND)
        self.assertEqual(mail.outbox[0].to, [self.controller.email])
        self.assertIn("control", str(mail.outbox[0].subject))

        # The controller gives his approval
        mail.outbox = []
        self.post(
            reverse("resource-validate-control", kwargs={"pk": self.resource.id}),
            data={"validation": True},
            content_type="application/json",
            user=self.controller,
        )
        self.resource.refresh_from_db()
        # Status should move from CONTROL_BOUND to INSTRUCTION_UNBOUND
        self.assertEqual(self.resource.status, ResourceStatus.INSTRUCTION_UNBOUND)
        # Instructor 1 should be notified
        self.assertEqual(mail.outbox[0].to, [self.instructor_1.email])
        self.assertIn("instruction", str(mail.outbox[0].subject))
        self.assertEqual(mail.outbox[0].to, [self.instructor_1.email])

        # instructor 1 finishes his turn
        self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection_1.id}),
            content_type="application/json",
            user=self.instructor_1,
        )
        self.resource.refresh_from_db()
        self.assertNotIn(self.collection_1.id, self.resource.instruction_turns["unbound_copies"]["turns"])

        mail.outbox = []

        # instructor 2 finishes his turn
        self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection_2.id}),
            content_type="application/json",
            user=self.instructor_2,
        )
        self.resource.refresh_from_db()
        self.assertNotIn(self.collection_2.id, self.resource.instruction_turns["unbound_copies"]["turns"])

        # This should trigger control phase
        # The controller is notified
        self.assertEqual(self.resource.status, ResourceStatus.CONTROL_UNBOUND)
        self.assertEqual(mail.outbox[0].to, [self.controller.email])
        self.assertIn("control", str(mail.outbox[0].subject))

        # The controller gives his approval
        mail.outbox = []
        self.post(
            reverse("resource-validate-control", kwargs={"pk": self.resource.id}),
            data={"validation": True},
            content_type="application/json",
            user=self.controller,
        )
        self.resource.refresh_from_db()
        # Status should move from INSTRUCTION_UNBOUND to EDITION
        self.assertEqual(self.resource.status, ResourceStatus.EDITION)

    def test_no_control_notification_if_user_alert_false(self):
        self.controller.settings.setdefault("alerts", {}).setdefault(str(self.project.id), {})[
            AlertType.CONTROL.value
        ] = False
        self.controller.save()
        self.controller.refresh_from_db()

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

        self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection_1.id}),
            content_type="application/json",
            user=self.instructor_1,
        )
        self.resource.refresh_from_db()
        self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection_2.id}),
            content_type="application/json",
            user=self.instructor_2,
        )
        self.resource.refresh_from_db()

        # No email should be sent to the controller
        control_emails = [email for email in mail.outbox if "control" in str(email.subject)]
        actual_recipients = [email.to[0] for email in control_emails]
        self.assertNotIn(self.controller.email, actual_recipients)
        self.assertEqual(len(control_emails), 0)
