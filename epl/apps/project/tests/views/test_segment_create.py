from django_tenants.urlresolvers import reverse
from parameterized import parameterized

from epl.apps.project.models import Role, Segment
from epl.apps.project.models.choices import SegmentType
from epl.apps.project.tests.factories.segment import SegmentFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class SegmentCreateTest(TestCase):
    def setUp(self):
        super().setUp()
        self.segment1 = SegmentFactory()
        self.segment2 = SegmentFactory(collection=self.segment1.collection)

        self.instructor = UserWithRoleFactory(
            role=Role.INSTRUCTOR, project=self.segment1.collection.project, library=self.segment1.collection.library
        )

    def _get_url(self, name, url_params=None, query_params=None):
        url = reverse(name, kwargs=url_params or {})
        if query_params:
            from urllib.parse import urlencode

            query_params = urlencode(query_params)
            url = f"{url}?{query_params}"
        return url

    @parameterized.expand(
        [
            (Role.TENANT_SUPER_USER, 403),
            (Role.PROJECT_CREATOR, 403),
            (Role.INSTRUCTOR, 201),
            (Role.PROJECT_ADMIN, 201),
            (Role.PROJECT_MANAGER, 403),
            (Role.CONTROLLER, 403),
            (Role.GUEST, 403),
            (None, 403),
        ]
    )
    def test_create_segment(self, role, expected_status):
        collection = self.segment1.collection
        user = UserWithRoleFactory(role=role, project=collection.project, library=collection.library)
        self.assertEqual(
            collection.segments.count(),
            2,
        )

        data = {
            "content": "2010-2015",
            "improvable_elements": "2014",
            "exception": "2013",
            "improved_segment": self.segment1.id,
            "collection": collection.id,
        }
        response = self.post(
            self._get_url("segment-list"),
            data,
            content_type="application/json",
            user=user,
        )
        self.assertEqual(response.status_code, expected_status)

        if expected_status == 201:
            self.assertEqual(
                collection.segments.count(),
                3,
            )

    def test_create_segment_with_after_segment(self):
        segment3 = SegmentFactory(collection=self.segment1.collection)
        collection = self.segment1.collection

        self.assertEqual(self.segment1.order, 1)
        self.assertEqual(self.segment2.order, 2)
        self.assertEqual(segment3.order, 3)

        data = {
            "content": "2010-2015",
            "improvable_elements": "2014",
            "exception": "2013",
            "improved_segment": self.segment1.id,
            "collection": collection.id,
            "after_segment": str(self.segment1.id),
        }

        response = self.post(
            reverse("segment-list"),
            data,
            content_type="application/json",
            user=self.instructor,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(collection.segments.count(), 4)

        new_segment_id = response.data["id"]
        new_segment = Segment.objects.get(id=new_segment_id)
        self.assertEqual(new_segment.order, 2)

        self.segment1.refresh_from_db()
        self.assertEqual(self.segment1.order, 1)

        self.segment2.refresh_from_db()
        self.assertEqual(self.segment2.order, 3)

        segment3.refresh_from_db()
        self.assertEqual(segment3.order, 4)

    def test_default_values(self):
        collection = self.segment1.collection

        data = {
            "content": "2010-2015",
            "improvable_elements": "2014",
            "exception": "2013",
            "improved_segment": self.segment1.id,
            "collection": collection.id,
        }
        response = self.post(
            self._get_url("segment-list"),
            data,
            content_type="application/json",
            user=self.instructor,
        )

        self.assertEqual(
            response.data["order"],
            3,
        )
        self.assertEqual(
            response.data["segment_type"],
            SegmentType.BOUND,
        )
        self.assertEqual(
            response.data["created_by"],
            self.instructor.id,
        )
        self.assertFalse(response.data["retained"])

        response = self.post(
            self._get_url("segment-list"),
            data,
            content_type="application/json",
            user=self.instructor,
        )

        self.assertEqual(
            response.data["order"],
            4,
        )
