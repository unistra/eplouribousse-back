from django_tenants.urlresolvers import reverse
from parameterized import parameterized

from epl.apps.project.models import ResourceStatus, Role
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class FinishInstructionTurnTest(TestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory()
        self.library = LibraryFactory()
        self.instructor = UserWithRoleFactory(
            role=Role.INSTRUCTOR,
            project=self.project,
            library=self.library,
        )
        self.resource = ResourceFactory(project=self.project)
        self.collection = CollectionFactory(resource=self.resource, library=self.library, project=self.project)

    def test_anonymous_access_is_not_allowed(self):
        collection = CollectionFactory()
        response = self.post(reverse("collection-finish-instruction-turn", kwargs={"pk": collection.id}))
        self.response_unauthorized(response)

    @parameterized.expand(
        [
            ResourceStatus.POSITIONING,
            ResourceStatus.CONTROL_BOUND,
            ResourceStatus.CONTROL_UNBOUND,
        ]
    )
    def test_resource_must_be_in_instruction_bound_or_unbound_status(self, status):
        self.resource.status = status
        self.resource.instruction_turns = {
            "bound_copies": {
                "turns": [
                    {
                        "library": str(self.library.id),
                        "collection": str(self.collection.id),
                    }
                ]
            },
            "unbound_copies": {
                "turns": [
                    {
                        "library": str(self.library.id),
                        "collection": str(self.collection.id),
                    }
                ]
            },
        }
        self.resource.save()
        response = self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection.id}),
            user=self.instructor,
        )
        self.response_bad_request(response)

    def test_only_instructor_of_the_project_and_library_can_finish_instruction_turn(self):
        self.resource.status = ResourceStatus.INSTRUCTION_BOUND
        self.resource.instruction_turns = {
            "bound_copies": {
                "turns": [
                    {
                        "library": str(self.library.id),
                        "collection": str(self.collection.id),
                    }
                ]
            },
            "unbound_copies": {"turns": []},
        }
        self.resource.save()
        admin = UserWithRoleFactory(role=Role.PROJECT_ADMIN, project=self.project)
        response = self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection.id}),
            user=admin,
        )
        self.response_forbidden(response)

    def test_if_no_instruction_turns_are_left_the_turn_can_not_be_finished(self):
        self.resource.status = ResourceStatus.INSTRUCTION_BOUND
        self.resource.instruction_turns = {
            "bound_copies": {"turns": []},
            "unbound_copies": {"turns": []},
        }
        self.resource.save()
        response = self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection.id}),
            user=self.instructor,
        )
        self.response_bad_request(response)
        self.assertIn("Invalid turn data", str(response.data[0]))

    def test_invalid_instruction_turn_data_can_not_be_finished(self):
        self.resource.status = ResourceStatus.INSTRUCTION_BOUND
        self.resource.instruction_turns = {
            "bound_copies": {"turns": ""},
            "unbound_copies": {"turns": []},
        }
        self.resource.save()
        response = self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection.id}),
            user=self.instructor,
        )
        self.response_bad_request(response)
        self.assertIn("Invalid turn data", str(response.data[0]))

    def test_turn_must_match_library_and_collection(self):
        other_library = LibraryFactory()
        other_collection = CollectionFactory(resource=self.resource, library=other_library, project=self.project)
        self.resource.status = ResourceStatus.INSTRUCTION_BOUND
        self.resource.instruction_turns = {
            "bound_copies": {
                "turns": [
                    {
                        "library": str(other_library.id),
                        "collection": str(other_collection.id),
                    }
                ]
            },
            "unbound_copies": {"turns": []},
        }
        self.resource.save()
        response = self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection.id}),
            user=self.instructor,
        )
        self.response_forbidden(response)
        self.assertIn("Turn does not match library and collection", str(response.data[0]))

    def test_finish_turn_and_move_to_control(self):
        self.resource.status = ResourceStatus.INSTRUCTION_BOUND
        self.resource.instruction_turns = {
            "bound_copies": {
                "turns": [
                    {
                        "library": str(self.library.id),
                        "collection": str(self.collection.id),
                    }
                ]
            },
            "unbound_copies": {
                "turns": [
                    {
                        "library": str(self.library.id),
                        "collection": str(self.collection.id),
                    }
                ]
            },
        }
        self.resource.save()
        response = self.post(
            reverse("collection-finish-instruction-turn", kwargs={"pk": self.collection.id}),
            user=self.instructor,
        )
        self.response_ok(response)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.status, ResourceStatus.CONTROL_BOUND)
        self.assertEqual(
            self.resource.instruction_turns,
            {
                "bound_copies": {"turns": []},
                "unbound_copies": {
                    "turns": [
                        {
                            "library": str(self.library.id),
                            "collection": str(self.collection.id),
                        }
                    ]
                },
            },
        )
