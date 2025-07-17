from django_tenants.urlresolvers import reverse

from epl.apps.project.models import Role, UserRole
from epl.apps.project.tests.factories.project import PositioningProjectFactory, ProjectFactory, PublicProjectFactory
from epl.apps.project.tests.factories.user import ProjectCreatorFactory, UserFactory
from epl.tests import TestCase


class ProjectListTest(TestCase):
    def test_anonymous_user_can_list_public_projects(self):
        _project1 = PublicProjectFactory()
        _project2 = PublicProjectFactory()

        response = self.get(reverse("project-list"), user=None)
        self.response_ok(response)
        self.assertListEqual(
            sorted([project["id"] for project in response.data["results"]]),
            sorted([str(_project1.id), str(_project2.id)]),
        )

    def test_non_participant_cannot_list_private_projects(self):
        public_project = PublicProjectFactory()
        _private_project = ProjectFactory(is_private=True)

        response = self.get(reverse("project-list"), user=None)
        self.response_ok(response)
        self.assertEqual(response.data["results"][0]["id"], str(public_project.id))

    def test_participant_project_creator_can_list_private_projects(self):
        user = ProjectCreatorFactory()
        public_project = PublicProjectFactory()
        private_project = ProjectFactory(is_private=True)

        response = self.get(reverse("project-list"), user=user)
        self.response_ok(response)

        self.assertListEqual(
            sorted([project["id"] for project in response.data["results"]]),
            sorted([str(public_project.id), str(private_project.id)]),
        )

    def test_participant_can_view_project_only_if_it_is_launched(self):
        user = UserFactory()
        private_project = PositioningProjectFactory(is_private=True)
        UserRole.objects.create(user=user, project=private_project, role=Role.INSTRUCTOR, assigned_by=user)

        response = self.get(reverse("project-list"), user=user)
        self.response_ok(response)
        self.assertEqual(response.data["results"][0]["id"], str(private_project.id))
