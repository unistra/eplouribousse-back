import uuid

from django_tenants.urlresolvers import reverse
from parameterized import parameterized

from epl.apps.project.models import Role
from epl.apps.project.tests.factories.segment import SegmentFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class SegmentUpDownTest(TestCase):
    def setUp(self):
        super().setUp()
        self.segment1 = SegmentFactory()
        self.collection = self.segment1.collection
        self.segment2 = SegmentFactory(collection=self.collection)
        self.segment3 = SegmentFactory(collection=self.collection)

        self.instructor = UserWithRoleFactory(
            role=Role.INSTRUCTOR, project=self.collection.project, library=self.collection.library
        )

    @parameterized.expand(
        [
            (Role.TENANT_SUPER_USER, 403),
            (Role.PROJECT_CREATOR, 403),
            (Role.INSTRUCTOR, 200),
            (Role.PROJECT_ADMIN, 200),
            (Role.PROJECT_MANAGER, 403),
            (Role.CONTROLLER, 403),
            (Role.GUEST, 403),
            (None, 403),
        ]
    )
    def test_segment_move_up(self, role, expected_status):
        self.assertEqual(self.segment1.order, 1)
        self.assertEqual(self.segment2.order, 2)
        self.assertEqual(self.segment3.order, 3)

        user = UserWithRoleFactory(role=role, project=self.collection.project, library=self.collection.library)

        response = self.patch(
            reverse("segment-up", kwargs={"pk": str(self.segment2.id)}),
            content_type="application/json",
            user=user,
        )
        self.assertEqual(response.status_code, expected_status)

        if expected_status == 200:
            self.assertEqual(response.data["current_segment"]["id"], str(self.segment2.id))
            self.assertEqual(response.data["current_segment"]["order"], 1)
            self.assertEqual(response.data["previous_segment"]["id"], str(self.segment1.id))
            self.assertEqual(response.data["previous_segment"]["order"], 2)
            self.assertEqual(response.data["next_segment"], None)

            self.segment1.refresh_from_db()
            self.segment2.refresh_from_db()
            self.segment3.refresh_from_db()
            self.assertEqual(self.segment1.order, 2)
            self.assertEqual(self.segment2.order, 1)
            self.assertEqual(self.segment3.order, 3)

    @parameterized.expand(
        [
            (Role.TENANT_SUPER_USER, 403),
            (Role.PROJECT_CREATOR, 403),
            (Role.INSTRUCTOR, 200),
            (Role.PROJECT_ADMIN, 200),
            (Role.PROJECT_MANAGER, 403),
            (Role.CONTROLLER, 403),
            (Role.GUEST, 403),
            (None, 403),
        ]
    )
    def test_segment_move_down(self, role, expected_status):
        self.assertEqual(self.segment1.order, 1)
        self.assertEqual(self.segment2.order, 2)
        self.assertEqual(self.segment3.order, 3)

        user = UserWithRoleFactory(role=role, project=self.collection.project, library=self.collection.library)
        response = self.patch(
            reverse("segment-down", kwargs={"pk": str(self.segment2.id)}),
            content_type="application/json",
            user=user,
        )
        self.assertEqual(response.status_code, expected_status)

        if expected_status == 200:
            self.assertEqual(response.data["current_segment"]["id"], str(self.segment2.id))
            self.assertEqual(response.data["current_segment"]["order"], 3)
            self.assertEqual(response.data["next_segment"]["id"], str(self.segment3.id))
            self.assertEqual(response.data["next_segment"]["order"], 2)
            self.assertEqual(response.data["previous_segment"], None)

            self.segment1.refresh_from_db()
            self.segment2.refresh_from_db()
            self.segment3.refresh_from_db()
            self.assertEqual(self.segment1.order, 1)
            self.assertEqual(self.segment2.order, 3)
            self.assertEqual(self.segment3.order, 2)

    def test_move_top_segment_up_fails(self):
        response = self.patch(
            reverse("segment-up", kwargs={"pk": str(self.segment1.id)}),
            content_type="application/json",
            user=self.instructor,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("already at the top", str(response.content))

    def test_move_bottom_segment_down_fails(self):
        response = self.patch(
            reverse("segment-down", kwargs={"pk": str(self.segment3.id)}),
            content_type="application/json",
            user=self.instructor,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("already at the bottom", str(response.content))

    def test_segment_not_found(self):
        non_existent_id = uuid.uuid4()

        response = self.patch(
            reverse("segment-up", kwargs={"pk": str(non_existent_id)}),
            content_type="application/json",
            user=self.instructor,
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("No Segment matches the given query", str(response.content))
