from django_tenants.test.cases import TenantTestCase

from epl.apps.project.models import Project
from epl.apps.project.serializers.project import ProjectSerializer


class ProjectSerializerTest(TenantTestCase):
    def test_serializer_contains_expected_fields(self):
        project = Project.objects.create(name="Test", description="Description")
        serializer = ProjectSerializer(project)
        data = serializer.data

        expected_fields = ["id", "name", "description", "created_at", "updated_at"]
        self.assertEqual(set(data.keys()), set(expected_fields))

        self.assertEqual(data["name"], "Test")
        self.assertEqual(data["description"], "Description")

    def test_project_create_serializer(self):
        data = {"name": "New Project", "description": "New Description"}
        serializer = ProjectSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        project = serializer.save()
        self.assertEqual(project.name, "New Project")
