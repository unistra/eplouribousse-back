import uuid

from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context

from epl.apps.project.models import Role, UserRole
from epl.apps.project.models.library import Library
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import UserFactory
from epl.apps.user.models import User
from epl.tests import TestCase


class LibraryViewsTest(TestCase):
    def setUp(self):
        super().setUp()

        with tenant_context(self.tenant):
            # Create a user
            self.user = User.objects.create_user(username="user", email="user@eplouribouse.fr")
            self.library = Library.objects.create(
                name="Bibliothèque Nationale de Test",
                alias="BNT",
                code="67000",
            )

    def test_get_library_list(self):
        url = reverse("library-list")

        response = self.get(url, user=self.user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data.get("results")), 1)
        self.assertEqual(response.data["results"][0]["name"], self.library.name)


class ProjectLibraryViewsTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            # Create a user
            self.user = UserFactory()
            self.library = LibraryFactory()
            self.project = ProjectFactory()
            self.project.libraries.add(self.library)

    def test_add_library_to_project(self):
        library: Library = LibraryFactory()
        url = reverse("project-add-library", kwargs={"pk": self.project.id})
        data = {"library_id": str(library.id)}
        response = self.post(url, data=data, user=self.user)
        self.response_created(response)
        self.assertEqual(response.data["library_id"], str(library.id))
        self.assertEqual(
            self.project.libraries.count(),
            2,
        )

    def test_remove_library_from_project(self):
        library: Library = LibraryFactory()
        self.project.libraries.add(library)
        url = reverse("project-add-library", kwargs={"pk": self.project.id})
        response = self.delete(f"{url}?library_id={library.id}", user=self.user)
        self.response_no_content(response)
        self.assertEqual(
            self.project.libraries.count(),
            1,
        )

    def test_cannot_add_library_that_does_not_exist(self):
        url = reverse("project-add-library", kwargs={"pk": self.project.id})
        data = {"library_id": str(uuid.uuid4())}
        response = self.post(url, data=data, user=self.user)
        self.response_bad_request(response)

    def test_when_removing_a_library_user_roles_are_removed_too(self):
        UserRole.objects.create(
            project=self.project,
            user=self.user,
            library=self.library,
            role=Role.PROJECT_CREATOR,
            assigned_by=self.user,
        )
        url = reverse("project-add-library", kwargs={"pk": self.project.id})
        response = self.delete(f"{url}?library_id={self.library.id}", user=self.user)
        self.response_no_content(response)
        self.assertEqual(
            self.project.libraries.count(),
            0,
        )
        self.assertFalse(self.user.project_roles.filter(project=self.project, library=self.library).exists())

    def test_when_removing_a_library_collections_are_removed_too(self):
        _collection_1 = CollectionFactory()
        _collection_2 = CollectionFactory()
        self.project.collection_set.add(_collection_1, _collection_2)
        self.project.libraries.add(self.library)
        url = reverse("project-add-library", kwargs={"pk": self.project.id})
        response = self.delete(f"{url}?library_id={self.library.id}", user=self.user)
        self.response_no_content(response)
        self.assertEqual(
            self.project.libraries.count(),
            0,
        )
