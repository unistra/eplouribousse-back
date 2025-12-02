from django_tenants.test.cases import TenantTestCase

from epl.apps.project.models import Project, Role, UserRole
from epl.apps.project.serializers.project import ProjectUserSerializer
from epl.apps.user.models import User


class ProjectUserSerializerTest(TenantTestCase):
    def setUp(self):
        """Setup for tests"""
        # Create users
        self.user1 = User.objects.create(
            username="user1", email="user1@example.com", first_name="User", last_name="One"
        )
        self.user2 = User.objects.create(
            username="user2", email="user2@example.com", first_name="User", last_name="Two"
        )

        # Create a project
        self.project = Project.objects.create(name="Test Project")

        # Add roles to users
        self.role1 = UserRole.objects.create(user=self.user1, project=self.project, role=Role.INSTRUCTOR)
        self.role2 = UserRole.objects.create(user=self.user1, project=self.project, role=Role.PROJECT_MANAGER)
        self.role3 = UserRole.objects.create(user=self.user2, project=self.project, role=Role.GUEST)

    def test_ProjectUserSerializer(self):
        """Test the serialization of users for a project"""
        expected_data = [
            {
                "id": str(self.user1.id),
                "username": self.user1.username,
                "email": self.user1.email,
                "first_name": self.user1.first_name,
                "last_name": self.user1.last_name,
                "roles": [self.role1.role, self.role2.role],
            },
            {
                "id": str(self.user2.id),
                "username": self.user2.username,
                "email": self.user2.email,
                "first_name": self.user2.first_name,
                "last_name": self.user2.last_name,
                "roles": [self.role3.role],
            },
        ]

        serialized_data = ProjectUserSerializer([self.user1, self.user2], many=True).data

        # Check if the serialized data matches the expected data
        self.assertEqual(len(serialized_data), 2)
        self.assertEqual(serialized_data, expected_data)
