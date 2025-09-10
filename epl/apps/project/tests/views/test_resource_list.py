import uuid

from django_tenants.urlresolvers import reverse

from epl.apps.project.models import ResourceStatus, Role
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.segment import SegmentFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class FilterResourceOnStatusTest(TestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory()
        self.library = LibraryFactory()
        self.instructor = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library)

        self.resource_positioning = ResourceFactory(
            project=self.project,
            status=ResourceStatus.POSITIONING,
            instruction_turns={"bound_copies": {"turns": [str(self.library.id)]}, "unbound_copies": {"turns": []}},
        )
        _c1 = CollectionFactory(library=self.library, project=self.project, resource=self.resource_positioning)

        self.resource_instruction_bound_for_user = ResourceFactory(
            project=self.project,
            status=ResourceStatus.INSTRUCTION_BOUND,
            instruction_turns={"bound_copies": {"turns": [str(self.library.id)]}},
        )
        _c2 = CollectionFactory(
            library=self.library, project=self.project, resource=self.resource_instruction_bound_for_user
        )
        self.resource_instruction_bound_for_other_library = ResourceFactory(
            project=self.project,
            status=ResourceStatus.INSTRUCTION_BOUND,
            instruction_turns={"bound_copies": {"turns": [str(uuid.uuid4())]}},
        )
        _c3 = CollectionFactory(project=self.project, resource=self.resource_instruction_bound_for_other_library)

        self.resource_control_bound = ResourceFactory(
            project=self.project,
            status=ResourceStatus.CONTROL_BOUND,
            instruction_turns={"bound_copies": {"turns": []}, "unbound_copies": {"turns": [str(self.library.id)]}},
        )
        _c4 = CollectionFactory(project=self.project, library=self.library, resource=self.resource_control_bound)

        self.resource_instruction_unbound_for_user = ResourceFactory(
            project=self.project,
            status=ResourceStatus.INSTRUCTION_UNBOUND,
            instruction_turns={"bound_copies": {"turns": []}, "unbound_copies": {"turns": [str(self.library.id)]}},
        )
        _c5 = CollectionFactory(
            project=self.project, library=self.library, resource=self.resource_instruction_unbound_for_user
        )
        self.resource_instruction_unbound_for_other_library = ResourceFactory(
            project=self.project,
            status=ResourceStatus.INSTRUCTION_UNBOUND,
            instruction_turns={"bound_copies": {"turns": []}, "unbound_copies": {"turns": [str(uuid.uuid4())]}},
        )
        _c6 = CollectionFactory(project=self.project, resource=self.resource_instruction_unbound_for_other_library)

        self.resource_control_unbound = ResourceFactory(
            project=self.project,
            status=ResourceStatus.CONTROL_UNBOUND,
            instruction_turns={"unbound_copies": {"turns": [str(self.library.id)]}},
        )
        _c7 = CollectionFactory(project=self.project, library=self.library, resource=self.resource_control_unbound)

        self.resource_instruction_bound_without_segments = ResourceFactory(
            project=self.project,
            status=ResourceStatus.INSTRUCTION_BOUND,
            instruction_turns={"bound_copies": {"turns": [str(self.library.id)]}},
        )
        _c8 = CollectionFactory(
            project=self.project, library=self.library, resource=self.resource_instruction_bound_without_segments
        )
        self.resource_instruction_bound_with_segment = ResourceFactory(
            project=self.project,
            status=ResourceStatus.INSTRUCTION_BOUND,
            instruction_turns={"bound_copies": {"turns": [str(uuid.uuid4())]}},
        )
        _c9 = CollectionFactory(
            project=self.project, library=self.library, resource=self.resource_instruction_bound_with_segment
        )
        _segment = SegmentFactory(collection=_c9)

    def _get_url(self, name, url_params=None, query_params=None):
        url = reverse(name, kwargs=url_params or {})
        if query_params:
            from urllib.parse import urlencode

            query_params = urlencode(query_params)
            url = f"{url}?{query_params}"
        return url

    def test_filter_positioning_with_no_library(self):
        # We should see all resources with no segments, whatever the status

        query_params = {
            "project": self.project.id,
            "status": ResourceStatus.POSITIONING,
        }
        response = self.get(
            self._get_url("resource-list", query_params=query_params),
            user=self.instructor,
        )
        self.response_ok(response)
        self.assertEqual(
            response.data["count"],
            8,
        )

    def test_filter_positioning_with_library(self):
        # We should see resources with no segments having collections in the library
        # and whose turn it is to instruct
        query_params = {
            "project": self.project.id,
            "library": self.library.id,
            "status": ResourceStatus.POSITIONING,
        }
        response = self.get(
            self._get_url("resource-list", query_params=query_params),
            user=self.instructor,
        )
        self.response_ok(response)
        self.assertEqual(
            response.data["count"],
            6,
        )
        self.assertListEqual(
            sorted([result["id"] for result in response.data["results"]]),
            sorted(
                [
                    str(self.resource_positioning.id),
                    str(self.resource_instruction_bound_for_user.id),
                    str(self.resource_control_bound.id),
                    str(self.resource_instruction_unbound_for_user.id),
                    str(self.resource_control_unbound.id),
                    str(self.resource_instruction_bound_without_segments.id),
                ]
            ),
        )

    def test_filter_instruction_bound_and_no_library(self):
        query_params = {
            "project": self.project.id,
            "status": ResourceStatus.INSTRUCTION_BOUND,
        }
        response = self.get(
            self._get_url("resource-list", query_params=query_params),
            user=self.instructor,
        )
        self.response_ok(response)
        self.assertEqual(
            response.data["count"],
            4,
        )
        self.assertListEqual(
            sorted([result["id"] for result in response.data["results"]]),
            sorted(
                [
                    str(self.resource_instruction_bound_for_user.id),
                    str(self.resource_instruction_bound_for_other_library.id),
                    str(self.resource_instruction_bound_without_segments.id),
                    str(self.resource_instruction_bound_with_segment.id),
                ]
            ),
        )

    def test_filter_instruction_bound_for_instructor(self):
        query_params = {
            "project": self.project.id,
            "library": self.library.id,
            "status": ResourceStatus.INSTRUCTION_BOUND,
        }
        response = self.get(
            self._get_url("resource-list", query_params=query_params),
            user=self.instructor,
        )
        self.response_ok(response)
        self.assertEqual(
            response.data["count"],
            2,
        )
        self.assertListEqual(
            sorted([result["id"] for result in response.data["results"]]),
            sorted(
                [
                    str(self.resource_instruction_bound_for_user.id),
                    str(self.resource_instruction_bound_without_segments.id),
                ]
            ),
        )

    def test_filter_instruction_unbound_and_no_library(self):
        query_params = {
            "project": self.project.id,
            "status": ResourceStatus.INSTRUCTION_UNBOUND,
        }
        response = self.get(
            self._get_url("resource-list", query_params=query_params),
            user=self.instructor,
        )
        self.response_ok(response)
        self.assertEqual(
            response.data["count"],
            2,
        )
        self.assertListEqual(
            sorted([result["id"] for result in response.data["results"]]),
            sorted(
                [
                    str(self.resource_instruction_unbound_for_user.id),
                    str(self.resource_instruction_unbound_for_other_library.id),
                ]
            ),
        )

    def test_filter_instruction_unbound_for_instructor(self):
        query_params = {
            "project": self.project.id,
            "library": self.library.id,
            "status": ResourceStatus.INSTRUCTION_UNBOUND,
        }
        response = self.get(
            self._get_url("resource-list", query_params=query_params),
            user=self.instructor,
        )
        self.response_ok(response)
        self.assertEqual(
            response.data["count"],
            1,
        )
        self.assertListEqual(
            sorted([result["id"] for result in response.data["results"]]),
            sorted(
                [
                    str(self.resource_instruction_unbound_for_user.id),
                ]
            ),
        )

    def test_filter_control_bound(self):
        query_params = {
            "project": self.project.id,
            "status": ResourceStatus.CONTROL_BOUND,
        }
        response = self.get(
            self._get_url("resource-list", query_params=query_params),
            user=self.instructor,
        )
        self.response_ok(response)
        self.assertEqual(
            response.data["count"],
            1,
        )
        self.assertListEqual(
            sorted([result["id"] for result in response.data["results"]]),
            sorted(
                [
                    str(self.resource_control_bound.id),
                ]
            ),
        )

    def test_filter_control_bound_with_library(self):
        query_params = {
            "project": self.project.id,
            "library": self.library.id,
            "status": ResourceStatus.CONTROL_BOUND,
        }
        response = self.get(
            self._get_url("resource-list", query_params=query_params),
            user=self.instructor,
        )
        self.response_ok(response)
        self.assertEqual(
            response.data["count"],
            1,
        )
        self.assertListEqual(
            sorted([result["id"] for result in response.data["results"]]),
            sorted(
                [
                    str(self.resource_control_bound.id),
                ]
            ),
        )

    def test_filter_control_unbound(self):
        query_params = {
            "project": self.project.id,
            "status": ResourceStatus.CONTROL_UNBOUND,
        }
        response = self.get(
            self._get_url("resource-list", query_params=query_params),
            user=self.instructor,
        )
        self.response_ok(response)
        self.assertEqual(
            response.data["count"],
            1,
        )
        self.assertListEqual(
            sorted([result["id"] for result in response.data["results"]]),
            sorted(
                [
                    str(self.resource_control_unbound.id),
                ]
            ),
        )

    def test_filter_control_unbound_with_library(self):
        query_params = {
            "project": self.project.id,
            "library": self.library.id,
            "status": ResourceStatus.CONTROL_UNBOUND,
        }
        response = self.get(
            self._get_url("resource-list", query_params=query_params),
            user=self.instructor,
        )
        self.response_ok(response)
        self.assertEqual(
            response.data["count"],
            1,
        )
        self.assertListEqual(
            sorted([result["id"] for result in response.data["results"]]),
            sorted(
                [
                    str(self.resource_control_unbound.id),
                ]
            ),
        )

    def test_instruction_bound_and_against_library(self):
        other_library = LibraryFactory()
        _coll = CollectionFactory(
            project=self.project,
            library=other_library,
            resource=self.resource_instruction_bound_for_user,
        )
        query_params = {
            "project": self.project.id,
            "library": self.library.id,
            "against": other_library.id,
            "status": ResourceStatus.INSTRUCTION_BOUND,
        }
        response = self.get(
            self._get_url("resource-list", query_params=query_params),
            user=self.instructor,
        )
        self.response_ok(response)
        self.assertEqual(
            response.data["count"],
            1,
        )
        self.assertEqual(
            response.data["results"][0]["id"],
            str(self.resource_instruction_bound_for_user.id),
        )
