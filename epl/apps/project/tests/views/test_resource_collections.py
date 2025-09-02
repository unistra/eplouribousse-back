from django_tenants.urlresolvers import reverse
from parameterized import parameterized

from epl.apps.project.models import Role
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class ResourceCollectionsTest(TestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory()
        self.library = LibraryFactory()
        self.resource = ResourceFactory(project=self.project)
        self.collection1 = CollectionFactory(library=self.library, project=self.project, resource=self.resource)
        self.collection2 = CollectionFactory(library=self.library, project=self.project, resource=self.resource)

        self.other_project = ProjectFactory()
        self.other_collection = CollectionFactory(
            library=self.library, project=self.other_project, resource=self.resource
        )

        self.default_user = UserWithRoleFactory(role=Role.GUEST, project=self.project)

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
    def test_get_resource_collections(self, role, expected_status):
        user = UserWithRoleFactory(role=role, project=self.project, library=self.library) if role else None

        url = reverse("resource-collections", args=[self.resource.id])
        response = self.get(url, user=user)

        self.assertEqual(response.status_code, expected_status)

        if expected_status == 200:
            self.assertIn("resource", response.data)
            self.assertIn("collections", response.data)

            self.assertEqual(response.data["resource"]["id"], str(self.resource.id))
            resource = response.data["resource"]
            self.assertIn("acl", resource)

            collections = response.data["collections"]
            self.assertEqual(len(collections), 2)
            self.assertIn("acl", collections[0])
            collection_ids = [collection["id"] for collection in collections]
            self.assertIn(str(self.collection1.id), collection_ids)
            self.assertIn(str(self.collection2.id), collection_ids)

            self.assertNotIn(str(self.other_collection.id), collection_ids)
