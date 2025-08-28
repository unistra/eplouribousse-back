from django_tenants.urlresolvers import reverse
from parameterized import parameterized

from epl.apps.project.models import ResourceStatus, Role
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class ResourceListTest(TestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory()
        self.library = LibraryFactory()
        self.instructor = UserWithRoleFactory(project=self.project, library=self.library, role=Role.INSTRUCTOR)
        self.resource = ResourceFactory()
        self.resource_project = ResourceFactory(project=self.project)
        self.resource_library = ResourceFactory(
            project=self.project,
            status=ResourceStatus.INSTRUCTION_BOUND,
            instruction_turns={"bound_copies": {"turns": [str(self.library.id)]}},
        )
        _collection = CollectionFactory(library=self.library, project=self.project, resource=self.resource_library)

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
    def test_list_resources(self, role, expected_status):
        user = UserWithRoleFactory(role=role, project=self.project, library=self.library)
        response = self.get(self._get_url("resource-list"), user=user)
        self.assertEqual(response.status_code, expected_status)
        self.assertEqual(
            response.data["count"],
            3,
        )

    def test_list_resources_for_project(self):
        query_params = {"project": self.project.id}
        response = self.get(self._get_url("resource-list", query_params=query_params))
        self.response_ok(response)
        self.assertEqual(
            response.data["count"],
            2,
        )
        self.assertListEqual(
            sorted([result["id"] for result in response.data["results"]]),
            sorted([str(self.resource_project.id), str(self.resource_library.id)]),
        )

    def test_list_resources_for_library(self):
        query_params = {"library": self.library.id}
        response = self.get(self._get_url("resource-list", query_params=query_params))
        self.response_ok(response)
        self.assertEqual(
            response.data["count"],
            1,
        )
        self.assertEqual(
            response.data["results"][0]["id"],
            str(self.resource_library.id),
        )

    def test_list_shows_resources_that_should_be_instructed(self):
        query_params = {"project": self.project.id}
        response = self.get(self._get_url("resource-list", query_params=query_params), user=self.instructor)
        self.response_ok(response)
        self.assertEqual(
            response.data["count"],
            2,
        )
        result_with_instruction = [result for result in response.data["results"] if result["should_instruct"]]
        self.assertEqual(len(result_with_instruction), 1)
        self.assertEqual(
            result_with_instruction[0]["id"],
            str(self.resource_library.id),
        )

    def _get_url(self, name, url_params=None, query_params=None):
        url = reverse(name, kwargs=url_params or {})
        if query_params:
            from urllib.parse import urlencode

            query_params = urlencode(query_params)
            url = f"{url}?{query_params}"
        return url
