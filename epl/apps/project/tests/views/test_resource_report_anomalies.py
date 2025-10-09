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
