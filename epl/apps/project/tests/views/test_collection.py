from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context

from epl.apps.project.models import Project, Library, Collection
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.user.models import User
from epl.tests import TestCase

FIXTURES_BASE_PATH = (
    Path(settings.DJANGO_ROOT) / "apps" / "project" / "tests" / "fixtures" / "serializers" / "collection"
)


class CollectionViewSetTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.user = User.objects.create_user(email="test_user@eplouribousse.fr")
            self.project = Project.objects.create(name="test_project", description="Test project for collections")
            self.library = Library.objects.create(name="test_library", alias="TL", code="12345")

    def test_list_collections_success(self):
        response = self.get(reverse("collection-list"), user=self.user)
        self.response_ok(response)

    def test_import_csv_success(self):
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

            response = self.post(reverse("collection-import_csv"), data=data, user=self.user, format="multipart")

            self.response_ok(response)
            self.assertEqual(response.status_code, 200)
            self.response_ok(response)

            self.assertTrue(Collection.objects.filter(library=self.library, project=self.project).exists())
            #
            # # afficher les collections créées
            # collections = Collection.objects.filter(library=self.library, project=self.project)
            # print(f"Collections created: {collections.count()}")
            # for collection in collections:
            #     print(
            #         f"Collection ID: {collection.id},"
            #         f"Title: {collection.title},"
            #         f"Code: {collection.code},"
            #         f"library: {collection.library},"
            #         f"Project: {collection.project},"
            #         f"ISSN: {collection.issn},"
            #     )

    # Validation tests for the import CSV endpoint
    def test_missing_csv_file_validation(self):
        data = {
            "library": self.library.id,
            "project": self.project.id,
        }
        response = self.post(reverse("collection-import_csv"), data=data, user=self.user, format="multipart")

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

            response = self.post(reverse("collection-import_csv"), data=data, user=self.user, format="multipart")

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

            response = self.post(reverse("collection-import_csv"), data=data, user=self.user, format="multipart")

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

        response = self.post(reverse("collection-import_csv"), data=data, user=self.user, format="multipart")
        self.assertEqual(response.status_code, 400)
        # Check that the response contains the right error message
        response_data = response.json()
        self.assertIn("csvFile", response_data)
        self.assertIn("Error in rows(s)", response_data["csvFile"])

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

        response = self.post(reverse("collection-import_csv"), data=data, user=self.user, format="multipart")
        self.assertEqual(response.status_code, 400)
        # Check that the response contains the right error message
        response_data = response.json()
        self.assertIn("csvFile", response_data)
        self.assertIn("Error in rows(s)", response_data["csvFile"])

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

        response = self.post(reverse("collection-import_csv"), data=data, user=self.user, format="multipart")

        self.assertEqual(response.status_code, 400)

        response_data = response.json()
        self.assertIn("csvFile", response_data)
        self.assertIn("Error in rows(s)", response_data["csvFile"])

    def test_import_csv_with_multiple_errors(self):
        invalid_csv_file_path = FIXTURES_BASE_PATH / "multiple_errors_collection.csv"

        with invalid_csv_file_path.open("rb") as csv_file:
            uploaded_file = SimpleUploadedFile(
                name="invalid_collection_multiple_errors.csv", content=csv_file.read(), content_type="text/csv"
            )

            data = {
                "csv_file": uploaded_file,
                "library": self.library.id,
                "project": self.project.id,
            }

        response = self.post(reverse("collection-import_csv"), data=data, user=self.user, format="multipart")

        self.assertEqual(response.status_code, 400)

        response_data = response.json()
        self.assertIn("csvFile", response_data)
        self.assertIn("Error in rows(s) 1, 2, 3", response_data["csvFile"])

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

        response = self.post(reverse("collection-import_csv"), data=data, user=self.user, format="multipart")

        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn("csvFile", response_data)
        self.assertIn("Column(s) Titre missing in the CSV file.", response_data["csvFile"])

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

        response = self.post(reverse("collection-import_csv"), data=data, user=self.user, format="multipart")

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
