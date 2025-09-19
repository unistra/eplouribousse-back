import uuid

from django_tenants.urlresolvers import reverse
from parameterized import parameterized

from epl.apps.project.models import Role, Segment
from epl.apps.project.tests.factories.segment import SegmentFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class SegmentDestroyTest(TestCase):
    def setUp(self):
        super().setUp()
        self.segment = SegmentFactory()
        self.collection = self.segment.collection

        self.instructor = UserWithRoleFactory(
            role=Role.INSTRUCTOR, project=self.collection.project, library=self.collection.library
        )

    @parameterized.expand(
        [
            (Role.TENANT_SUPER_USER, 403),
            (Role.PROJECT_CREATOR, 403),
            (Role.INSTRUCTOR, 204),
            (Role.PROJECT_ADMIN, 403),
            (Role.PROJECT_MANAGER, 403),
            (Role.CONTROLLER, 403),
            (Role.GUEST, 403),
            (None, 403),
        ]
    )
    def test_destroy_segment(self, role, expected_status):
        user = UserWithRoleFactory(role=role, project=self.collection.project, library=self.collection.library)

        segment_count_before = Segment.objects.filter(collection=self.collection).count()

        response = self.delete(
            reverse("segment-detail", kwargs={"pk": self.segment.id}),
            user=user,
        )

        self.assertEqual(response.status_code, expected_status)

        segment_count_after = Segment.objects.filter(collection=self.collection).count()

        if expected_status == 204:
            self.assertEqual(segment_count_after, segment_count_before - 1)
            self.assertFalse(Segment.objects.filter(id=self.segment.id).exists())
        else:
            self.assertEqual(segment_count_after, segment_count_before)
            self.assertTrue(Segment.objects.filter(id=self.segment.id).exists())

    def test_destroy_nonexistent_segment(self):
        non_existent_id = uuid.uuid4()
        response = self.delete(
            reverse("segment-detail", kwargs={"pk": non_existent_id}),
            user=self.instructor,
        )

        self.assertEqual(response.status_code, 404)

    def test_destroy_segment_updates_segment_after_order(self):
        segment2 = SegmentFactory(collection=self.collection, order=2)
        segment3 = SegmentFactory(collection=self.collection, order=3)
        segment4 = SegmentFactory(collection=self.collection, order=4)

        response = self.delete(
            reverse("segment-detail", kwargs={"pk": segment2.id}),
            user=self.instructor,
        )

        self.assertEqual(response.status_code, 204)

        segment3.refresh_from_db()
        segment4.refresh_from_db()
        self.assertEqual(segment3.order, 2)
        self.assertEqual(segment4.order, 3)

    def test_order_when_destroy_cascade(self):
        segment2 = SegmentFactory(collection=self.collection, order=2)
        SegmentFactory(collection=self.collection, order=3, improved_segment=self.segment)
        SegmentFactory(collection=self.collection, order=4, improved_segment=self.segment)
        segment5 = SegmentFactory(collection=self.collection, order=5)

        response = self.delete(
            reverse("segment-detail", kwargs={"pk": self.segment.id}),
            user=self.instructor,
        )

        self.assertEqual(response.status_code, 204)

        segment2.refresh_from_db()
        segment5.refresh_from_db()

        # Refresh remaining segments from DB and check their order
        remaining_segments = Segment.objects.filter(collection=self.collection).order_by("order")
        self.assertEqual(list(remaining_segments), [segment2, segment5])
        self.assertEqual(segment2.order, 1)
        self.assertEqual(segment5.order, 2)

        expected_orders = list(range(1, len(remaining_segments) + 1))
        actual_orders = [segment.order for segment in remaining_segments]
        self.assertEqual(actual_orders, expected_orders)
