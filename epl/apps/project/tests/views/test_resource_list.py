import uuid

from django_tenants.urlresolvers import reverse
from parameterized import parameterized

from epl.apps.project.models import ProjectStatus, ResourceStatus, Role
from epl.apps.project.models.collection import Arbitration
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.segment import SegmentFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class FilterResourceOnStatusTest(TestCase):
    # =============================
    # SETUP
    # =============================
    def setUp(self):
        super().setUp()
        self._setup_project_and_libraries()
        self._setup_resources_for_main_project()
        self._setup_positioning_filter_project()

    def _setup_project_and_libraries(self):
        self.project = ProjectFactory()
        self.library1 = LibraryFactory()
        self.library2 = LibraryFactory()
        self.project.libraries.add(self.library1, self.library2)
        self.instructor = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library1)

    def _setup_resources_for_main_project(self):
        self._create_positioning_resource()
        self._create_instruction_bound_resources()
        self._create_control_bound_resource()
        self._create_instruction_unbound_resources()
        self._create_control_unbound_resource()

    def _create_positioning_resource(self):
        # RESOURCE 1
        self.resource_positioning = ResourceFactory(
            project=self.project,
            status=ResourceStatus.POSITIONING,
        )
        _c1 = CollectionFactory(library=self.library1, project=self.project, resource=self.resource_positioning)
        CollectionFactory(library=self.library2, project=self.project, resource=self.resource_positioning)
        self.resource_positioning.instruction_turns = {
            "bound_copies": {"turns": [{"library": str(self.library1.id), "collection": str(_c1.id)}]},
            "unbound_copies": {"turns": []},
        }
        self.resource_positioning.save()

    def _create_instruction_bound_resources(self):
        # RESOURCE 2
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

        # RESOURCE 3
        self.resource_instruction_bound_for_other_library = ResourceFactory(
            project=self.project,
            status=ResourceStatus.INSTRUCTION_BOUND,
            instruction_turns={
                "bound_copies": {"turns": [{"library": str(uuid.uuid4()), "collection": str(uuid.uuid4())}]}
            },
        )
        CollectionFactory(project=self.project, resource=self.resource_instruction_bound_for_other_library)
        CollectionFactory(project=self.project, resource=self.resource_instruction_bound_for_other_library)

        # RESOURCE 4
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

        # RESOURCE 5
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
        SegmentFactory(collection=_c9)
        self.resource_instruction_bound_with_segment.instruction_turns = {
            "bound_copies": {"turns": [{"library": str(uuid.uuid4()), "collection": str(_c9.id)}]}
        }
        self.resource_instruction_bound_with_segment.save()

    def _create_resource_with_unbound_turn(self, status):
        """Helper to create a resource with an unbound turn for library1."""
        resource = ResourceFactory(
            project=self.project,
            status=status,
        )
        collection = CollectionFactory(project=self.project, library=self.library1, resource=resource)
        CollectionFactory(project=self.project, library=self.library2, resource=resource)
        resource.instruction_turns = {
            "bound_copies": {"turns": []},
            "unbound_copies": {"turns": [{"library": str(self.library1.id), "collection": str(collection.id)}]},
        }
        resource.save()
        return resource

    def _create_control_bound_resource(self):
        # RESOURCE 6
        self.resource_control_bound = self._create_resource_with_unbound_turn(
            status=ResourceStatus.CONTROL_BOUND,
        )

    def _create_instruction_unbound_resources(self):
        # RESOURCE 7
        self.resource_instruction_unbound_for_user = self._create_resource_with_unbound_turn(
            status=ResourceStatus.INSTRUCTION_UNBOUND,
        )

        # RESOURCE 8
        self.resource_instruction_unbound_for_other_library = ResourceFactory(
            project=self.project,
            status=ResourceStatus.INSTRUCTION_UNBOUND,
        )
        CollectionFactory(project=self.project, resource=self.resource_instruction_unbound_for_other_library)
        CollectionFactory(project=self.project, resource=self.resource_instruction_unbound_for_other_library)
        self.resource_instruction_unbound_for_other_library.instruction_turns = {
            "bound_copies": {"turns": []},
            "unbound_copies": {"turns": [{"library": str(uuid.uuid4()), "collection": str(uuid.uuid4())}]},
        }
        self.resource_instruction_bound_for_other_library.save()

    def _create_control_unbound_resource(self):
        # RESOURCE 9
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

    def _setup_positioning_filter_project(self):
        """Setup project and resources for positioning filter tests."""
        self.project_positioning_filter = ProjectFactory(status=ProjectStatus.LAUNCHED)
        self.project_positioning_filter.libraries.add(self.library1, self.library2)

        # Resource with POSITIONING status and no arbitration
        self.resource_positioning_no_arbitration = ResourceFactory(
            project=self.project_positioning_filter,
            status=ResourceStatus.POSITIONING,
        )
        CollectionFactory(
            library=self.library1,
            project=self.project_positioning_filter,
            resource=self.resource_positioning_no_arbitration,
        )
        CollectionFactory(
            library=self.library2,
            project=self.project_positioning_filter,
            resource=self.resource_positioning_no_arbitration,
        )

        # Resource with POSITIONING status and arbitration
        self.resource_positioning_with_arbitration = ResourceFactory(
            project=self.project_positioning_filter,
            status=ResourceStatus.POSITIONING,
            arbitration=Arbitration.ONE,
        )
        CollectionFactory(
            library=self.library1,
            project=self.project_positioning_filter,
            resource=self.resource_positioning_with_arbitration,
        )
        CollectionFactory(
            library=self.library2,
            project=self.project_positioning_filter,
            resource=self.resource_positioning_with_arbitration,
        )

        # Resource with INSTRUCTION_BOUND status and no arbitration
        self.resource_instruction_bound_no_arbitration = ResourceFactory(
            project=self.project_positioning_filter,
            status=ResourceStatus.INSTRUCTION_BOUND,
            arbitration=Arbitration.NONE,
        )
        _c_instruction = CollectionFactory(
            library=self.library1,
            project=self.project_positioning_filter,
            resource=self.resource_instruction_bound_no_arbitration,
        )
        CollectionFactory(
            library=self.library2,
            project=self.project_positioning_filter,
            resource=self.resource_instruction_bound_no_arbitration,
        )
        self.resource_instruction_bound_no_arbitration.instruction_turns = {
            "bound_copies": {"turns": [{"library": str(self.library1.id), "collection": str(_c_instruction.id)}]}
        }
        self.resource_instruction_bound_no_arbitration.save()

    def _get_url(self, name, url_params=None, query_params=None):
        url = reverse(name, kwargs=url_params or {})
        if not query_params:
            return url

        from urllib.parse import urlencode

        params = []
        for k, v in query_params.items():
            if isinstance(v, (list, tuple)):
                for item in v:
                    params.append((f"{k}[]", item))
            else:
                params.append((k, v))
        query_string = urlencode(params, doseq=True)
        # show literal brackets for readability (encoded value is still valid)
        query_string = query_string.replace("%5B%5D", "[]")
        return f"{url}?{query_string}"

    def test_filter_positioning_with_no_library(self):
        # We should see all resources with no segments, whatever the status

        query_params = {
            "project": self.project.id,
            "status": [ResourceStatus.POSITIONING],
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
            "library": self.library1.id,
            "status": [ResourceStatus.POSITIONING],
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
            "status": [ResourceStatus.INSTRUCTION_BOUND],
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
            "status": [ResourceStatus.INSTRUCTION_BOUND],
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
            "status": [ResourceStatus.INSTRUCTION_UNBOUND],
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

    @parameterized.expand(
        [
            (ResourceStatus.INSTRUCTION_UNBOUND, "resource_instruction_unbound_for_user", True),
            (ResourceStatus.CONTROL_BOUND, "resource_control_bound", True),
            (ResourceStatus.CONTROL_UNBOUND, "resource_control_unbound", True),
            (ResourceStatus.CONTROL_BOUND, "resource_control_bound", False),
            (ResourceStatus.CONTROL_UNBOUND, "resource_control_unbound", False),
        ]
    )
    def test_filter_status(self, status, resource_attr_name, include_library):
        query_params = {
            "project": self.project.id,
            "status": [status],
        }
        if include_library:
            query_params["library"] = self.library1.id

        response = self.get(
            self._get_url("resource-list", query_params=query_params),
            user=self.instructor,
        )
        self.response_ok(response)
        self.assertEqual(response.data["count"], 1)
        expected_resource = getattr(self, resource_attr_name)
        self.assertListEqual(
            sorted([result["id"] for result in response.data["results"]]),
            [str(expected_resource.id)],
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
            "status": [ResourceStatus.INSTRUCTION_BOUND],
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

    @parameterized.expand(
        [
            (10, ResourceStatus.POSITIONING, "resource_positioning_no_arbitration", False),
            (10, ResourceStatus.POSITIONING, "resource_positioning_no_arbitration", True),
            (20, ResourceStatus.INSTRUCTION_BOUND, "resource_instruction_bound_no_arbitration", False),
            (20, ResourceStatus.INSTRUCTION_BOUND, "resource_instruction_bound_no_arbitration", True),
        ]
    )
    def test_filter_with_positioning_filter(self, positioning_filter, status, resource_attr_name, include_library):
        query_params = {
            "project": self.project_positioning_filter.id,
            "status": [status],
            "positioning_filter": positioning_filter,
        }
        if include_library:
            query_params["library"] = self.library1.id

        response = self.get(
            self._get_url("resource-list", query_params=query_params),
            user=self.instructor,
        )
        self.response_ok(response)
        self.assertEqual(response.data["count"], 1)
        expected_resource = getattr(self, resource_attr_name)
        self.assertEqual(
            response.data["results"][0]["id"],
            str(expected_resource.id),
        )

    def test_filter_arbitration_all(self):
        # Test arbitration=all - should return resources with arbitration type 0 or 1

        resource_positioning_with_arbitration_zero = ResourceFactory(
            project=self.project_positioning_filter,
            status=ResourceStatus.POSITIONING,
            arbitration=Arbitration.ZERO,
        )
        CollectionFactory(
            library=self.library1,
            project=self.project_positioning_filter,
            resource=resource_positioning_with_arbitration_zero,
        )
        CollectionFactory(
            library=self.library2,
            project=self.project_positioning_filter,
            resource=resource_positioning_with_arbitration_zero,
        )

        query_params = {
            "project": self.project_positioning_filter.id,
            "status": [ResourceStatus.POSITIONING],
            "arbitration": "all",
        }
        response = self.get(
            self._get_url("resource-list", query_params=query_params),
            user=self.instructor,
        )
        self.response_ok(response)
        self.assertEqual(response.data["count"], 2)
        result_ids = sorted([result["id"] for result in response.data["results"]])
        expected_ids = sorted(
            [
                str(self.resource_positioning_with_arbitration.id),
                str(resource_positioning_with_arbitration_zero.id),
            ]
        )
        self.assertListEqual(result_ids, expected_ids)
