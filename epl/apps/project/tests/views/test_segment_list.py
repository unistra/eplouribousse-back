from django_tenants.urlresolvers import reverse
from parameterized import parameterized

from epl.apps.project.models import Role
from epl.apps.project.tests.factories.segment import SegmentFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class SegmentListTest(TestCase):
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
            (Role.TENANT_SUPER_USER, 200),
            (Role.PROJECT_CREATOR, 200),
            (Role.INSTRUCTOR, 200),
            (Role.PROJECT_ADMIN, 200),
            (Role.PROJECT_MANAGER, 200),
            (Role.CONTROLLER, 200),
            (Role.GUEST, 200),
            (None, 200),
        ]
    )
    def test_list_segments(self, role, expected_status):
        user = UserWithRoleFactory(
            role=role, project=self.segment1.collection.project, library=self.segment1.collection.library
        )
        response = self.get(
            self._get_url("segment-list", query_params={"resource_id": str(self.segment1.collection.resource.id)}),
            user=user,
        )
        self.assertEqual(response.status_code, expected_status)
        self.assertEqual(
            len(response.data),
            2,
        )

    def test_list_ordering(self):
        SegmentFactory(collection=self.segment1.collection)

        response = self.get(
            self._get_url(
                "segment-list",
                query_params={"resource_id": str(self.segment1.collection.resource.id), "ordering": "order"},
            ),
            user=self.instructor,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["order"], 1)
        self.assertEqual(response.data[1]["order"], 2)
        self.assertEqual(response.data[2]["order"], 3)

    def test_invalid_resource(self):
        response = self.get(
            self._get_url("segment-list", query_params={"resource_id": self.instructor.id}), user=self.instructor
        )
        self.assertEqual(response.status_code, 404)

        response = self.get(self._get_url("segment-list"), user=self.instructor)
        self.assertEqual(response.status_code, 400)
