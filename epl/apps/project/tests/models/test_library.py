from django.db import IntegrityError
from django_tenants.test.cases import TenantTestCase

from epl.apps.project.models.library import Library


class LibraryTest(TenantTestCase):
    def setUp(self):
        # Create a library instance for testing
        self.library = Library.objects.create(
            name="Bibliothèque Nationale de Test",
            alias="BNT",
            code="67000",
        )

    def test_library_creation(self):
        self.assertEqual(self.library.name, "Bibliothèque Nationale de Test")
        self.assertEqual(self.library.alias, "BNT")
        self.assertEqual(self.library.code, "67000")

    def test_library_str_representation(self):
        self.assertEqual(str(self.library), "Bibliothèque Nationale de Test")

    def test_library_unique_name_constraint(self):
        """Test that creating a library with the same name raises an IntegrityError"""
        with self.assertRaises(IntegrityError):
            Library.objects.create(
                name=self.library.name,
                alias="BNT1",
                code="67001",
            )

    def test_library_unique_code_constraint(self):
        with self.assertRaises(IntegrityError):
            Library.objects.create(
                name="Bibliothèque Nationale de Test 3",
                alias="BNT3",
                code=self.library.code,
            )
