from epl.apps.project.models.library import Library
from epl.apps.project.serializers.library import LibrairySerializer
from epl.tests import TenantTestCase


class TestLibrarySerializer(TenantTestCase):
    def setUp(self):
        self.library = Library.objects.create(name="Bibliothèque Nationale de Test", alias="BNT", code="67000")

    def test_create_library_with_valid_data(self):
        serializer = LibrairySerializer(self.library)
        library_data = serializer.data

        self.assertEqual(self.library.name, library_data["name"])
        self.assertEqual(self.library.alias, library_data["alias"])
        self.assertEqual(self.library.code, library_data["code"])

        expected_fields = ["id", "name", "alias", "code", "created_at", "updated_at"]
        self.assertEqual(set(library_data.keys()), set(expected_fields))

    def test_update_library(self):
        updated_data = {
            "name": "Nouvelle Bibliothèque Nationale de Test",
            "alias": "NBNT",
            "code": "67001",
        }

        serializer = LibrairySerializer(self.library, data=updated_data)
        self.assertTrue(serializer.is_valid())
        updated_library = serializer.save()

        self.assertEqual(updated_library.name, updated_data["name"])
        self.assertEqual(updated_library.alias, updated_data["alias"])
        self.assertEqual(updated_library.code, updated_data["code"])
