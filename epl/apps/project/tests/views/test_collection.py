from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context

from epl.apps.project.models import Collection, Library, Project
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
        print(f"Response status: {response.status_code}")
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

            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.content}")
            self.response_ok(response)
            self.assertEqual(response.status_code, 200)
            self.response_ok(response)

            self.assertTrue(Collection.objects.filter(library=self.library, project=self.project).exists())

            # afficher les collections créées
            collections = Collection.objects.filter(library=self.library, project=self.project)
            print(f"Collections created: {collections.count()}")
            for collection in collections:
                print(
                    f"Collection ID: {collection.id},"
                    f"Title: {collection.title},"
                    f"Code: {collection.code},"
                    f"library: {collection.library},"
                    f"Project: {collection.project},"
                    f"ISSN: {collection.issn},"
                )
