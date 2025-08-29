from django_tenants.urlresolvers import reverse
from parameterized import parameterized

from epl.apps.project.models import Role
from epl.apps.project.tests.factories.segment import SegmentFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class SegmentPartialUpdateTest(TestCase):
    def setUp(self):
        super().setUp()
        self.segment = SegmentFactory()
        self.collection = self.segment.collection

        self.instructor = UserWithRoleFactory(
            role=Role.INSTRUCTOR, project=self.collection.project, library=self.collection.library
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
            (Role.INSTRUCTOR, 200),
            (Role.PROJECT_ADMIN, 403),
            (Role.PROJECT_MANAGER, 403),
            (Role.CONTROLLER, 403),
            (Role.GUEST, 403),
            (None, 403),
        ]
    )
    def test_partial_update_segment(self, role, expected_status):
        user = UserWithRoleFactory(role=role, project=self.collection.project, library=self.collection.library)

        updated_content = "Updated content"
        data = {
            "content": updated_content,
        }

        response = self.patch(
            self._get_url("segment-detail", url_params={"pk": self.segment.id}),
            data,
            content_type="application/json",
            user=user,
        )

        self.assertEqual(response.status_code, expected_status)

        if expected_status == 200:
            self.segment.refresh_from_db()
            self.assertEqual(self.segment.content, updated_content)

    @staticmethod
    def get_response_and_test_status_and_refresh_db(self, data):
        response = self.patch(
            self._get_url("segment-detail", url_params={"pk": self.segment.id}),
            data,
            content_type="application/json",
            user=self.instructor,
        )

        self.assertEqual(response.status_code, 200)
        self.segment.refresh_from_db()

        return response

    def test_update_multiple_fields(self):
        updated_content = "Updated segment content"
        updated_improvable_elements = "Updated improvable elements"
        updated_exception = "Updated exception"

        data = {
            "content": updated_content,
            "improvable_elements": updated_improvable_elements,
            "exception": updated_exception,
        }

        self.get_response_and_test_status_and_refresh_db(self, data)

        self.assertEqual(self.segment.content, updated_content)
        self.assertEqual(self.segment.improvable_elements, updated_improvable_elements)
        self.assertEqual(self.segment.exception, updated_exception)

    def test_update_order_is_ignored(self):
        original_order = self.segment.order
        updated_order = original_order + 1
        content = "Updated content"

        data = {
            "content": content,
            "order": updated_order,
        }

        self.get_response_and_test_status_and_refresh_db(self, data)

        self.assertEqual(self.segment.order, original_order)
        self.assertEqual(self.segment.content, content)

    def test_update_without_required_fields(self):
        original_content = self.segment.content
        updated_improvable_elements = "Only updating improvable elements"

        data = {
            "improvable_elements": updated_improvable_elements,
        }

        self.get_response_and_test_status_and_refresh_db(self, data)

        self.assertEqual(self.segment.content, original_content)
        self.assertEqual(self.segment.improvable_elements, updated_improvable_elements)
