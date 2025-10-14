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
        self.library1 = LibraryFactory()
        self.library2 = LibraryFactory()
        self.project.libraries.add(self.library1, self.library2)
        self.instructor = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library1)

        self.resource_positioning = ResourceFactory(
            project=self.project,
            status=ResourceStatus.POSITIONING,
        )
        _c1 = CollectionFactory(library=self.library1, project=self.project, resource=self.resource_positioning)
        # We need a duplicate collection in another library to ensure the resource is not filtered out
        CollectionFactory(library=self.library2, project=self.project, resource=self.resource_positioning)

        self.resource_positioning.instruction_turns = (
            {
                "bound_copies": {"turns": [{"library": str(self.library1.id), "collection": str(_c1.id)}]},
                "unbound_copies": {"turns": []},
            },
        )
        self.resource_positioning.save()

        self.resource_instruction_bound_for_user = ResourceFactory(
            project=self.project,
            status=ResourceStatus.INSTRUCTION_BOUND,
        )
        _c2 = CollectionFactory(
            library=self.library1, project=self.project, resource=self.resource_instruction_bound_for_user
        )
        CollectionFactory(
            library=self.library2, project=self.project, resource=self.resource_instruction_bound_for_user
        )

        self.resource_instruction_bound_for_user.instruction_turns = {
            "bound_copies": {"turns": [{"library": str(self.library1.id), "collection": str(_c2.id)}]}
        }
        self.resource_instruction_bound_for_user.save()
        self.resource_instruction_bound_for_other_library = ResourceFactory(
            project=self.project,
            status=ResourceStatus.INSTRUCTION_BOUND,
            instruction_turns={
                "bound_copies": {"turns": [{"library": str(uuid.uuid4()), "collection": str(uuid.uuid4())}]}
            },
        )
        _c3 = CollectionFactory(project=self.project, resource=self.resource_instruction_bound_for_other_library)
        CollectionFactory(project=self.project, resource=self.resource_instruction_bound_for_other_library)

        self.resource_control_bound = ResourceFactory(
            project=self.project,
            status=ResourceStatus.CONTROL_BOUND,
        )
        _c4 = CollectionFactory(project=self.project, library=self.library1, resource=self.resource_control_bound)
        CollectionFactory(project=self.project, library=self.library2, resource=self.resource_control_bound)
        self.resource_control_bound.instruction_turns = {
            "bound_copies": {"turns": []},
            "unbound_copies": {"turns": [{"library": str(self.library1.id), "collection": str(_c4.id)}]},
        }
        self.resource_control_bound.save()

        self.resource_instruction_unbound_for_user = ResourceFactory(
            project=self.project,
            status=ResourceStatus.INSTRUCTION_UNBOUND,
        )
        _c5 = CollectionFactory(
            project=self.project, library=self.library1, resource=self.resource_instruction_unbound_for_user
        )
        CollectionFactory(
            project=self.project, library=self.library2, resource=self.resource_instruction_unbound_for_user
        )
        self.resource_instruction_unbound_for_user.instruction_turns = {
            "bound_copies": {"turns": []},
            "unbound_copies": {"turns": [{"library": str(self.library1.id), "collection": str(_c5.id)}]},
        }
        self.resource_instruction_unbound_for_user.save()

        self.resource_instruction_unbound_for_other_library = ResourceFactory(
            project=self.project,
            status=ResourceStatus.INSTRUCTION_UNBOUND,
        )
        _c6 = CollectionFactory(project=self.project, resource=self.resource_instruction_unbound_for_other_library)
        CollectionFactory(project=self.project, resource=self.resource_instruction_unbound_for_other_library)
        self.resource_instruction_unbound_for_other_library.instruction_turns = (
            {
                "bound_copies": {"turns": []},
                "unbound_copies": {"turns": [{"library": str(uuid.uuid4()), "collection": str(uuid.uuid4())}]},
            },
        )
        self.resource_instruction_bound_for_other_library.save()

        self.resource_control_unbound = ResourceFactory(
            project=self.project,
            status=ResourceStatus.CONTROL_UNBOUND,
        )
        _c7 = CollectionFactory(project=self.project, library=self.library1, resource=self.resource_control_unbound)
        CollectionFactory(project=self.project, library=self.library2, resource=self.resource_control_unbound)
        self.resource_control_unbound.instruction_turns = {
            "unbound_copies": {"turns": [{"library": str(self.library1.id), "collection": str(_c7.id)}]},
        }
        self.resource_control_unbound.save()

        self.resource_instruction_bound_without_segments = ResourceFactory(
            project=self.project,
            status=ResourceStatus.INSTRUCTION_BOUND,
        )
        _c8 = CollectionFactory(
            project=self.project, library=self.library1, resource=self.resource_instruction_bound_without_segments
        )
        CollectionFactory(
            project=self.project, library=self.library2, resource=self.resource_instruction_bound_without_segments
        )
        self.resource_instruction_bound_without_segments.instruction_turns = {
            "bound_copies": {"turns": [{"library": str(self.library1.id), "collection": str(_c8.id)}]},
        }
        self.resource_instruction_bound_without_segments.save()

        self.resource_instruction_bound_with_segment = ResourceFactory(
            project=self.project,
            status=ResourceStatus.INSTRUCTION_BOUND,
        )
        _c9 = CollectionFactory(
            project=self.project, library=self.library1, resource=self.resource_instruction_bound_with_segment
        )
        CollectionFactory(
            project=self.project, library=self.library2, resource=self.resource_instruction_bound_with_segment
        )
        _segment = SegmentFactory(collection=_c9)
        self.resource_instruction_bound_with_segment.instruction_turns = {
            "bound_copies": {"turns": [{"library": str(uuid.uuid4()), "collection": str(_c9.id)}]}
        }
        self.resource_instruction_bound_with_segment.save()

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
            9,
        )

    def test_filter_positioning_with_library(self):
        # We should see resources with no segments having collections in the library
        # and whose turn it is to instruct
        query_params = {
            "project": self.project.id,
            "library": self.library1.id,
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
            "library": self.library1.id,
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
            "library": self.library1.id,
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
            "library": self.library1.id,
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
            "library": self.library1.id,
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
            "library": self.library1.id,
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
