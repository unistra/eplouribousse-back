from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context
from parameterized import parameterized

from epl.apps.project.models import Collection, Role
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase

FIXTURES_BASE_PATH = (
    Path(settings.DJANGO_ROOT) / "apps" / "project" / "tests" / "fixtures" / "serializers" / "collection"
)


class CollectionDeletePermissionTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.project = ProjectFactory()
            self.library = LibraryFactory()
            self.collection = CollectionFactory(project=self.project, library=self.library)
            self.user_factory = UserWithRoleFactory(project=self.project, library=self.library)

    @parameterized.expand(
        [
            (Role.PROJECT_CREATOR, True, 204),  # Peut supprimer
            (Role.INSTRUCTOR, False, 403),  # Ne peut pas supprimer
            (Role.PROJECT_ADMIN, False, 403),
            (Role.PROJECT_MANAGER, False, 403),
            (Role.CONTROLLER, False, 403),
            (Role.GUEST, False, 403),
            (None, False, 403),  # Anonymous user
        ]
    )
    def test_delete_collection_permissions(self, role, should_succeed, expected_status):
        """Test les permissions de suppression pour chaque rôle"""
        user = UserWithRoleFactory(role=role, project=self.project, library=self.library)
        response = self.delete(reverse("collection-detail", kwargs={"pk": self.collection.id}), user=user)
        self.assertEqual(response.status_code, expected_status)

        collection_exists = Collection.objects.filter(id=self.collection.id).exists()
        if should_succeed:
            self.assertFalse(collection_exists, f"Collection should be deleted for {role}")
        else:
            self.assertTrue(collection_exists, f"Collection should still exist for {role}")


class CollectionViewSetTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.project = ProjectFactory.create()
            self.library = LibraryFactory.create()

            self.project_admin = UserWithRoleFactory(
                role=Role.PROJECT_ADMIN, project=self.project, library=self.library
            )

            # Create a user with no particular rights but authenticated
            self.guest = UserWithRoleFactory(role=Role.GUEST)

            # Create a user with project creator role
            self.project_creator = UserWithRoleFactory(role=Role.PROJECT_CREATOR)

    @parameterized.expand(
        [
            (Role.PROJECT_CREATOR, True, 200),
            (Role.INSTRUCTOR, True, 200),
            (Role.PROJECT_ADMIN, True, 200),
            (Role.PROJECT_MANAGER, True, 200),
            (Role.CONTROLLER, True, 200),
            (Role.GUEST, True, 200),
            (None, True, 200),  # Anonymous user
        ]
    )
    def test_list_collections_success(self, role, should_succeed, expected_status):
        user = UserWithRoleFactory(role=role, project=self.project, library=self.library)
        response = self.get(reverse("collection-list"), user=user)
        self.assertEqual(response.status_code, expected_status)
        self.response_ok(response)

    @parameterized.expand(
        [
            (Role.PROJECT_CREATOR, True, 200),
            (Role.INSTRUCTOR, False, 403),
            (Role.PROJECT_ADMIN, False, 403),
            (Role.PROJECT_MANAGER, False, 403),
            (Role.CONTROLLER, False, 403),
            (Role.GUEST, False, 403),
            (None, False, 401),  # Anonymous user
        ]
    )
    def test_import_csv_permissions(self, role, should_succeed, expected_status):
        if role is None:
            user = None
        else:
            user = UserWithRoleFactory(role=role, project=self.project, library=self.library)

        valid_csv_file_path = FIXTURES_BASE_PATH / "valid_collection.csv"
        with valid_csv_file_path.open("rb") as csv_file:
            uploaded_file = SimpleUploadedFile(
                name="valid_collection.csv", content=csv_file.read(), content_type="text/csv"
            )
            data = {
                "csv_file": uploaded_file,
                "library": self.library.id,
                "project": self.project.id,
            }
            response = self.post(reverse("collection-import_csv"), data=data, user=user, format="multipart")

        self.assertEqual(response.status_code, expected_status)
        if should_succeed:
            self.assertTrue(Collection.objects.filter(library=self.library, project=self.project).exists())
        else:
            self.assertFalse(Collection.objects.filter(library=self.library, project=self.project).exists())

    # Validation tests for the import CSV endpoint
    def test_missing_csv_file_validation(self):
        data = {
            "library": self.library.id,
            "project": self.project.id,
        }
        response = self.post(reverse("collection-import_csv"), data=data, user=self.project_creator, format="multipart")

        self.assertEqual(response.status_code, 400)
        self.assertIn("csv_file", response.data)

    def test_invalid_library_id_validation(self):
        valid_csv_file_path = FIXTURES_BASE_PATH / "valid_collection.csv"

        with valid_csv_file_path.open("rb") as csv_file:
            uploaded_file = SimpleUploadedFile(
                name="valid_collection.csv", content=csv_file.read(), content_type="text/csv"
            )
            invalid_library_id = uuid4()

            data = {
                "csv_file": uploaded_file,
                "library": invalid_library_id,
                "project": self.project.id,
            }

            response = self.post(
                reverse("collection-import_csv"), data=data, user=self.project_creator, format="multipart"
            )

            self.assertEqual(response.status_code, 400)
            self.assertIn("library", response.data)

    def test_invalid_project_id_validation(self):
        valid_csv_file_path = FIXTURES_BASE_PATH / "valid_collection.csv"

        with valid_csv_file_path.open("rb") as csv_file:
            uploaded_file = SimpleUploadedFile(
                name="valid_collection.csv", content=csv_file.read(), content_type="text/csv"
            )
            invalid_project_id = uuid4()

            data = {
                "csv_file": uploaded_file,
                "library": self.library.id,
                "project": invalid_project_id,
            }

            response = self.post(
                reverse("collection-import_csv"), data=data, user=self.project_creator, format="multipart"
            )

            self.assertEqual(response.status_code, 400)
            self.assertIn("project", response.data)

    def test_import_csv_with_missing_title(self):
        invalid_csv_file_path = FIXTURES_BASE_PATH / "missing_title_value_collection.csv"

        with invalid_csv_file_path.open("rb") as csv_file:
            uploaded_file = SimpleUploadedFile(
                name="invalid_collection_missing_title.csv", content=csv_file.read(), content_type="text/csv"
            )

            data = {
                "csv_file": uploaded_file,
                "library": self.library.id,
                "project": self.project.id,
            }

        response = self.post(reverse("collection-import_csv"), data=data, user=self.project_creator, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("csv_file", response.data)
        self.assertEqual(int(response.data["csv_file"][0]["row"]), 2)
        self.assertIn("string_too_short", str(response.data["csv_file"][0]["errors"]))

    def test_import_csv_with_missing_code(self):
        invalid_csv_file_path = FIXTURES_BASE_PATH / "missing_code_value_collection.csv"

        with invalid_csv_file_path.open("rb") as csv_file:
            uploaded_file = SimpleUploadedFile(
                name="invalid_collection_missing_code.csv", content=csv_file.read(), content_type="text/csv"
            )

            data = {
                "csv_file": uploaded_file,
                "library": self.library.id,
                "project": self.project.id,
            }

        response = self.post(reverse("collection-import_csv"), data=data, user=self.project_creator, format="multipart")
        self.assertEqual(response.status_code, 400)
        # Check that the response contains the right error message
        self.assertIn("csv_file", response.data)
        self.assertEqual(int(response.data["csv_file"][0]["row"]), 2)

    def test_import_csv_with_invalid_issn(self):
        invalid_csv_file_path = FIXTURES_BASE_PATH / "invalid_issn_collection.csv"

        with invalid_csv_file_path.open("rb") as csv_file:
            uploaded_file = SimpleUploadedFile(
                name="invalid_collection_invalid_issn.csv", content=csv_file.read(), content_type="text/csv"
            )

            data = {
                "csv_file": uploaded_file,
                "library": self.library.id,
                "project": self.project.id,
            }

        response = self.post(reverse("collection-import_csv"), data=data, user=self.project_creator, format="multipart")

        self.assertEqual(response.status_code, 400)

        self.assertIn("csv_file", response.data)
        self.assertEqual(int(response.data["csv_file"][0]["row"]), 2)

    def test_import_csv_with_missing_title_field(self):
        invalid_csv_file_path = FIXTURES_BASE_PATH / "missing_title_field_collection.csv"

        with invalid_csv_file_path.open("rb") as csv_file:
            uploaded_file = SimpleUploadedFile(
                name="invalid_collection_missing_title_field.csv", content=csv_file.read(), content_type="text/csv"
            )

            data = {
                "csv_file": uploaded_file,
                "library": self.library.id,
                "project": self.project.id,
            }

        response = self.post(reverse("collection-import_csv"), data=data, user=self.project_creator, format="multipart")

        self.assertEqual(response.status_code, 400)
        self.assertIn("csv_file", response.data)
        self.assertIn("Column(s) Titre missing in the CSV file.", response.data["csv_file"])

    def test_import_csv_rollback_on_error(self):
        invalid_csv_file_path = FIXTURES_BASE_PATH / "multiple_errors_collection.csv"

        with invalid_csv_file_path.open("rb") as csv_file:
            uploaded_file = SimpleUploadedFile(
                name="multiple_errors_collection", content=csv_file.read(), content_type="text/csv"
            )

            data = {
                "csv_file": uploaded_file,
                "library": self.library.id,
                "project": self.project.id,
            }

        response = self.post(reverse("collection-import_csv"), data=data, user=self.project_creator, format="multipart")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Collection.objects.filter(library=self.library, project=self.project).exists())


class CollectionListViewTest(TestCase):
    def setUp(self):
        self.collections = []
        super().setUp()

    def create_collection(self, count=1):
        with tenant_context(self.tenant):
            for _ in range(count):
                self.collections.append(CollectionFactory())

    def test_anonymous_user_can_list_collections(self):
        self.create_collection(1)
        response = self.get(reverse("collection-list"), user=None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["next"], None)

    def test_collection_list(self):
        self.create_collection(15)
        response = self.get(reverse("collection-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 15)
        self.assertEqual(response.data["next"], 2)

    def test_collection_list_can_be_filtered_on_project(self):
        project_a = ProjectFactory()
        collection_project_a = CollectionFactory(project=project_a)
        _ = CollectionFactory()
        url = f"{reverse('collection-list')}?{urlencode({'project': project_a.id})}"
        response = self.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(collection_project_a.id))

    def test_collection_list_can_be_filtered_on_library(self):
        library_a = LibraryFactory()
        collection_a = CollectionFactory(library=library_a)
        _ = CollectionFactory()
        url = f"{reverse('collection-list')}?{urlencode({'library': library_a.id})}"
        response = self.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(collection_a.id))
