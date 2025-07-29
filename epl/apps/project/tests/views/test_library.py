import uuid

from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context
from parameterized import parameterized

from epl.apps.project.models import Role, UserRole
from epl.apps.project.models.library import Library
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import ProjectCreatorFactory, UserWithRoleFactory
from epl.tests import TestCase


class LibraryViewsTest(TestCase):
    def setUp(self):
        super().setUp()

        with tenant_context(self.tenant):
            self.library1 = LibraryFactory()
            self.library2 = LibraryFactory()

            self.project = ProjectFactory()

    @parameterized.expand(
        [
            (Role.PROJECT_CREATOR, 200),
            (Role.INSTRUCTOR, 200),
            (Role.PROJECT_ADMIN, 200),
            (Role.PROJECT_MANAGER, 200),
            (Role.CONTROLLER, 200),
            (Role.GUEST, 200),
            (None, 200),
        ]
    )
    def test_list_and_retrieve_library_permissions(self, role, expected_status_code):
        user = UserWithRoleFactory(role=role, project=self.project, library=self.library1)
        response_list = self.get(reverse("library-list"), user=user)

        self.assertEqual(response_list.status_code, expected_status_code)
        self.assertEqual(len(response_list.data["results"]), 2)

        response_retrieve = self.get(reverse("library-detail", kwargs={"pk": self.library1.id}), user=user)
        self.assertEqual(response_retrieve.status_code, expected_status_code)
        self.assertEqual(response_retrieve.data["id"], str(self.library1.id))


class ProjectLibraryViewsTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            # Create a user
            self.user = ProjectCreatorFactory()
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
        self.project.collections.add(_collection_1, _collection_2)
        self.project.libraries.add(self.library)
        url = reverse("project-add-library", kwargs={"pk": self.project.id})
        response = self.delete(f"{url}?library_id={self.library.id}", user=self.user)
        self.response_no_content(response)
        self.assertEqual(
            self.project.libraries.count(),
            0,
        )
