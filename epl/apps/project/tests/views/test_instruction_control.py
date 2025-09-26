from django_tenants.urlresolvers import reverse
from parameterized import parameterized
from rest_framework import status

from epl.apps.project.models import ResourceStatus, Role
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class InstructionControlTest(TestCase):
    def setUp(self):
        # Set up initial data for the tests
        super().setUp()
        self.project = ProjectFactory()
        self.user = UserWithRoleFactory(role=Role.CONTROLLER, project=self.project)
        self.library = LibraryFactory(project=self.project)
        self.collection = CollectionFactory(project=self.project, library=self.library)
        self.resource = ResourceFactory(
            project=self.project,
            status=ResourceStatus.CONTROL_BOUND,
            instruction_turns={
                "bound_copies": {"turns": [{"library": str(self.library.id), "collection": str(self.collection.id)}]},
                "unbound_copies": {"turns": [{"library": str(self.library.id), "collection": str(self.collection.id)}]},
            },
        )

    def test_anonymous_access_is_forbidden(self):
        response = self.post(
            reverse("resource-validate-control", kwargs={"pk": self.resource.id}),
            data={"validation": True},
        )
        self.response_unauthorized(response)

    @parameterized.expand(
        [
            (Role.GUEST, status.HTTP_403_FORBIDDEN),
            (Role.PROJECT_CREATOR, status.HTTP_403_FORBIDDEN),
            (Role.PROJECT_ADMIN, status.HTTP_403_FORBIDDEN),
            (Role.PROJECT_MANAGER, status.HTTP_403_FORBIDDEN),
            (Role.INSTRUCTOR, status.HTTP_403_FORBIDDEN),
            (Role.CONTROLLER, status.HTTP_200_OK),
        ]
    )
    def test_non_controller_access_is_forbidden(self, role, expected_status):
        non_controller_user = UserWithRoleFactory(role=role, project=self.project, library=self.library)
        response = self.post(
            reverse("resource-validate-control", kwargs={"pk": self.resource.id}),
            data={"validation": True},
            user=non_controller_user,
        )
        if role == Role.CONTROLLER:
            print(response.data, response.status_code)
        self.assertEqual(expected_status, response.status_code)

    @parameterized.expand(
        [
            (ResourceStatus.INSTRUCTION_BOUND, status.HTTP_400_BAD_REQUEST),
            (ResourceStatus.INSTRUCTION_UNBOUND, status.HTTP_400_BAD_REQUEST),
            (ResourceStatus.POSITIONING, status.HTTP_400_BAD_REQUEST),
            (ResourceStatus.EDITION, status.HTTP_400_BAD_REQUEST),
            (ResourceStatus.CONTROL_BOUND, status.HTTP_200_OK),
            (ResourceStatus.CONTROL_UNBOUND, status.HTTP_200_OK),
        ]
    )
    def test_resource_must_be_in_control_status(self, status, expected_status):
        self.resource.status = status
        self.resource.save(update_fields=["status"])

        response = self.post(
            reverse("resource-validate-control", kwargs={"pk": self.resource.id}),
            data={"validation": True},
            user=self.user,
        )
        if response.status_code != expected_status:
            print(response.data)
        self.assertEqual(expected_status, response.status_code)

    def test_status_is_updated_to_instruction_unbound_after_control_bound_validation(self):
        self.resource.status = ResourceStatus.CONTROL_BOUND
        self.resource.save(update_fields=["status"])

        response = self.post(
            reverse("resource-validate-control", kwargs={"pk": self.resource.id}),
            data={"validation": True},
            user=self.user,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.resource.refresh_from_db()
        self.assertEqual(ResourceStatus.INSTRUCTION_UNBOUND, self.resource.status)

    def test_status_is_updated_to_edition_after_control_unbound_validation(self):
        self.resource.status = ResourceStatus.CONTROL_UNBOUND
        self.resource.save(update_fields=["status"])

        response = self.post(
            reverse("resource-validate-control", kwargs={"pk": self.resource.id}),
            data={"validation": True},
            user=self.user,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.resource.refresh_from_db()
        self.assertEqual(ResourceStatus.EDITION, self.resource.status)
