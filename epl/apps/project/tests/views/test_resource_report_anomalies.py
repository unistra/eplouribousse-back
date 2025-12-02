from django_tenants.urlresolvers import reverse
from parameterized import parameterized

from epl.apps.project.models import ResourceStatus, Role, Segment
from epl.apps.project.models.choices import SegmentType
from epl.apps.project.tests.factories.anomaly import AnomalyFactory
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.segment import SegmentFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class AnomaliesTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory()
        self.library = LibraryFactory()
        self.project.libraries.add(self.library)
        self.instructor = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library)
        self.controller = UserWithRoleFactory(role=Role.CONTROLLER, project=self.project)
        self.admin = UserWithRoleFactory(role=Role.PROJECT_ADMIN, project=self.project)

        self.resource = ResourceFactory(
            project=self.project,
            status=ResourceStatus.INSTRUCTION_BOUND,
        )
        self.collection = CollectionFactory(
            project=self.project,
            resource=self.resource,
            library=self.library,
            created_by=self.instructor,
        )
        self.segment = SegmentFactory(
            collection=self.collection, segment_type=SegmentType.BOUND, created_by=self.instructor
        )
        self.anomaly1 = AnomalyFactory(
            segment=self.segment,
            resource=self.resource,
            created_by=self.instructor,
        )
        self.anomaly2 = AnomalyFactory(
            segment=self.segment,
            resource=self.resource,
            created_by=self.instructor,
        )


class ReportAnomaliesViewTest(AnomaliesTestCase):
    def setUp(self):
        super().setUp()

    def test_report_anonymous_user_can_not_report_anomalies(self):
        response = self.patch(
            reverse("resource-report-anomalies", kwargs={"pk": self.resource.pk}),
            user=None,
        )
        self.response_unauthorized(response)

    def test_instructor_can_report_anomalies(self):
        response = self.patch(
            reverse("resource-report-anomalies", kwargs={"pk": self.resource.pk}),
            user=self.instructor,
        )
        self.response_ok(response)
        self.resource.refresh_from_db()
        self.assertEqual(
            self.resource.status,
            ResourceStatus.ANOMALY_BOUND,
        )

    def test_controller_can_report_anomalies(self):
        response = self.patch(
            reverse("resource-report-anomalies", kwargs={"pk": self.resource.pk}),
            user=self.controller,
        )
        self.response_ok(response)
        self.resource.refresh_from_db()
        self.assertEqual(
            self.resource.status,
            ResourceStatus.ANOMALY_BOUND,
        )

    @parameterized.expand(
        [
            ResourceStatus.POSITIONING,
            ResourceStatus.ANOMALY_BOUND,
            ResourceStatus.ANOMALY_UNBOUND,
            ResourceStatus.EDITION,
        ]
    )
    def test_resource_must_be_in_instruction_or_control_status(self, resource_status):
        self.resource.status = resource_status
        self.resource.save(update_fields=["status"])
        response = self.patch(
            reverse("resource-report-anomalies", kwargs={"pk": self.resource.pk}),
            user=self.controller,
        )
        self.response_bad_request(response)
        self.assertIn("status", response.data)
        self.resource.refresh_from_db()


class ResetResourceInstructionViewTest(AnomaliesTestCase):
    def setUp(self):
        super().setUp()

    def test_anonymous_user_can_not_reset_instruction(self):
        response = self.patch(
            reverse("resource-reset-instruction", kwargs={"pk": self.resource.pk}),
            user=None,
        )
        self.response_unauthorized(response)

    def test_instructor_can_not_reset_instruction(self):
        response = self.patch(
            reverse("resource-reset-instruction", kwargs={"pk": self.resource.pk}),
            user=self.instructor,
        )
        self.response_forbidden(response)

    def test_controller_can_not_reset_instruction(self):
        response = self.patch(
            reverse("resource-reset-instruction", kwargs={"pk": self.resource.pk}),
            user=self.controller,
        )
        self.response_forbidden(response)

    def test_admin_can_reset_instruction(self):
        self.resource.status = ResourceStatus.ANOMALY_BOUND
        self.resource.save(update_fields=["status"])
        _bound_segment = SegmentFactory(
            collection=self.collection,
            segment_type=SegmentType.BOUND,
            created_by=self.admin,
        )
        response = self.patch(
            reverse("resource-reset-instruction", kwargs={"pk": self.resource.pk}),
            user=self.admin,
        )
        self.response_ok(response)
        self.resource.refresh_from_db()
        self.assertEqual(
            self.resource.status,
            ResourceStatus.INSTRUCTION_BOUND,
        )
        # All segments must be deleted
        self.assertFalse(Segment.objects.filter(collection__in=self.resource.collections.all()).exists())


class ReassignResourceInstructionTurnViewTest(AnomaliesTestCase):
    def setUp(self):
        super().setUp()

    def test_anonymous_user_can_not_reassign_instruction_turn(self):
        response = self.patch(
            reverse("resource-reassign-instruction-turn", kwargs={"pk": self.resource.pk}),
            user=None,
        )
        self.response_unauthorized(response)

    def test_instructor_can_not_reassign_instruction_turn(self):
        response = self.patch(
            reverse("resource-reassign-instruction-turn", kwargs={"pk": self.resource.pk}),
            user=self.instructor,
        )
        self.response_forbidden(response)

    def test_controller_can_not_reassign_instruction_turn(self):
        response = self.patch(
            reverse("resource-reassign-instruction-turn", kwargs={"pk": self.resource.pk}),
            user=self.controller,
        )
        self.response_forbidden(response)

    def test_admin_can_reassign_instruction_turn(self):
        self.resource.status = ResourceStatus.ANOMALY_BOUND
        self.resource.save(update_fields=["status"])
        _bound_segment = SegmentFactory(
            collection=self.collection,
            segment_type=SegmentType.BOUND,
            created_by=self.admin,
        )
        response = self.patch(
            reverse("resource-reassign-instruction-turn", kwargs={"pk": self.resource.pk}),
            user=self.admin,
            data={"controller": True},
            content_type="application/json",
        )
        self.response_ok(response)

    def test_when_reassigning_to_controller_the_turns_are_empty(self):
        self.resource.status = ResourceStatus.ANOMALY_BOUND
        self.resource.instruction_turns = {
            "bound_copies": {
                "turns": [
                    {"library": str(self.library.id), "collection": str(self.instructor.id)},
                    {"library": None, "collection": None},
                ]
            },
            "unbound_copies": {
                "turns": [
                    {"library": str(self.library.id), "collection": str(self.instructor.id)},
                    {"library": None, "collection": None},
                ]
            },
            "turns": [
                {"library": str(self.library.id), "collection": str(self.instructor.id)},
                {"library": None, "collection": None},
            ],
        }
        self.resource.save(update_fields=["status", "instruction_turns"])
        _bound_segment = SegmentFactory(
            collection=self.collection,
            segment_type=SegmentType.BOUND,
            created_by=self.admin,
        )
        response = self.patch(
            reverse("resource-reassign-instruction-turn", kwargs={"pk": self.resource.pk}),
            user=self.admin,
            data={"controller": True},
            content_type="application/json",
        )
        self.response_ok(response)
        self.resource.refresh_from_db()
        self.assertEqual(
            self.resource.status,
            ResourceStatus.CONTROL_BOUND,
        )
        # Turns must be empty
        self.assertEqual(len(self.resource.instruction_turns["bound_copies"]["turns"]), 0)

    def test_when_reassigning_to_instructor_the_turns_are_updated(self):
        self.resource.status = ResourceStatus.ANOMALY_BOUND
        self.resource.instruction_turns = {
            "bound_copies": {
                "turns": [
                    {
                        "library": "49dc2153-3e45-48dd-8042-ad037e28f646",
                        "collection": "d299dc1f-4778-46b8-b75b-cd342e69cd8f",
                    },
                    {
                        "library": "2133c5f5-ca70-45b8-8eff-83455b0622fb",
                        "collection": "eb57b827-4729-41c7-a052-b804aece6638",
                    },
                    {"library": str(self.library.id), "collection": str(self.collection.id)},
                ],
            },
            "unbound_copies": {
                "turns": [
                    {
                        "library": "49dc2153-3e45-48dd-8042-ad037e28f646",
                        "collection": "d299dc1f-4778-46b8-b75b-cd342e69cd8f",
                    },
                    {
                        "library": "2133c5f5-ca70-45b8-8eff-83455b0622fb",
                        "collection": "eb57b827-4729-41c7-a052-b804aece6638",
                    },
                    {"library": str(self.library.id), "collection": str(self.collection.id)},
                ],
            },
            "turns": [
                {
                    "library": "49dc2153-3e45-48dd-8042-ad037e28f646",
                    "collection": "d299dc1f-4778-46b8-b75b-cd342e69cd8f",
                },
                {
                    "library": "2133c5f5-ca70-45b8-8eff-83455b0622fb",
                    "collection": "eb57b827-4729-41c7-a052-b804aece6638",
                },
                {"library": str(self.library.id), "collection": str(self.collection.id)},
            ],
        }
        self.resource.save(update_fields=["status", "instruction_turns"])
        _bound_segment = SegmentFactory(
            collection=self.collection,
            segment_type=SegmentType.BOUND,
            created_by=self.admin,
        )
        response = self.patch(
            reverse("resource-reassign-instruction-turn", kwargs={"pk": self.resource.pk}),
            user=self.admin,
            data={"library_id": str(self.library.id), "collection_id": str(self.collection.id)},
            content_type="application/json",
        )
        self.response_ok(response)
        self.resource.refresh_from_db()
        self.assertEqual(
            self.resource.status,
            ResourceStatus.INSTRUCTION_BOUND,
        )
        self.assertEqual(len(self.resource.instruction_turns["bound_copies"]["turns"]), 1)
        self.assertDictEqual(
            self.resource.instruction_turns["bound_copies"]["turns"][0],
            {"library": str(self.library.id), "collection": str(self.collection.id)},
        )
        self.assertEqual(len(self.resource.anomalies.filter(fixed=False)), 0)
        self.assertEqual(len(self.resource.anomalies.filter(fixed=True)), 2)
