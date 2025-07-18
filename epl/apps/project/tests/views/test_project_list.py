from datetime import timedelta

from django.utils.timezone import now
from django_tenants.urlresolvers import reverse

from epl.apps.project.models import Role, Status, UserRole
from epl.apps.project.tests.factories.project import (
    PositioningProjectFactory,
    PrivateProjectFactory,
    ProjectFactory,
    PublicProjectFactory,
)
from epl.apps.project.tests.factories.user import ProjectCreatorFactory, UserFactory
from epl.tests import TestCase


class ProjectListTest(TestCase):
    def test_anonymous_user_can_list_public_projects(self):
        project1 = PublicProjectFactory()
        project2 = PublicProjectFactory()
        _private_project = PrivateProjectFactory()

        response = self.get(reverse("project-list"), user=None)
        self.response_ok(response)
        self.assertListEqual(
            sorted([project["id"] for project in response.data["results"]]),
            sorted([str(project1.id), str(project2.id)]),
        )
        self.assertEqual(response.data["count"], 2)

    def test_anonymous_user_cannot_view_project_if_not_launched(self):
        # the project is private and not launched
        _private_project = ProjectFactory(
            is_private=False, status=Status.POSITIONING, active_after=now() + timedelta(days=1)
        )

        response = self.get(reverse("project-list"), user=None)
        self.response_ok(response)
        self.assertEqual(response.data["count"], 0)

    def test_non_participant_cannot_list_private_projects(self):
        public_project = PublicProjectFactory()
        _private_project = ProjectFactory(is_private=True)

        response = self.get(reverse("project-list"), user=None)
        self.response_ok(response)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(public_project.id))

    def test_project_creator_can_list_private_projects(self):
        user = ProjectCreatorFactory()
        public_project = PublicProjectFactory()
        private_project = ProjectFactory(is_private=True)

        response = self.get(reverse("project-list"), user=user)
        self.response_ok(response)

        self.assertListEqual(
            sorted([project["id"] for project in response.data["results"]]),
            sorted([str(public_project.id), str(private_project.id)]),
        )

    def test_instructor_can_view_project_only_if_it_is_launched(self):
        user = UserFactory()
        # the project is private and launched
        private_project = PositioningProjectFactory(is_private=True)
        UserRole.objects.create(user=user, project=private_project, role=Role.INSTRUCTOR, assigned_by=user)

        response = self.get(reverse("project-list"), user=user)
        self.response_ok(response)
        self.assertEqual(response.data["results"][0]["id"], str(private_project.id))

    def test_instructor_cannot_view_project_if_not_launched(self):
        user = UserFactory()
        # the project is private and not launched
        private_project = ProjectFactory(
            is_private=True, status=Status.POSITIONING, active_after=now() + timedelta(days=1)
        )
        UserRole.objects.create(user=user, project=private_project, role=Role.INSTRUCTOR, assigned_by=user)

        response = self.get(reverse("project-list"), user=user)
        self.response_ok(response)
        self.assertEqual(response.data["count"], 0)

    def test_controller_cannot_view_project_if_not_launched(self):
        user = UserFactory()
        # the project is private and not launched
        private_project = ProjectFactory(
            is_private=True, status=Status.POSITIONING, active_after=now() + timedelta(days=1)
        )
        UserRole.objects.create(user=user, project=private_project, role=Role.CONTROLLER, assigned_by=user)

        response = self.get(reverse("project-list"), user=user)
        self.response_ok(response)
        self.assertEqual(response.data["count"], 0)

    def test_guest_can_view_launched_project(self):
        user = UserFactory()
        # the project is private and launched
        private_project = PositioningProjectFactory(is_private=True)
        UserRole.objects.create(user=user, project=private_project, role=Role.GUEST, assigned_by=user)

        # user is not a guest in this other project
        _other_private_project = PositioningProjectFactory(is_private=True)

        response = self.get(reverse("project-list"), user=user)
        self.response_ok(response)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(private_project.id))

    def test_guest_cannot_view_project_if_not_launched(self):
        user = UserFactory()
        # the project is private and not launched
        private_project = ProjectFactory(
            is_private=True, status=Status.POSITIONING, active_after=now() + timedelta(days=1)
        )
        UserRole.objects.create(user=user, project=private_project, role=Role.GUEST, assigned_by=user)

        response = self.get(reverse("project-list"), user=user)
        self.response_ok(response)
        self.assertEqual(response.data["count"], 0)

    def test_archived_projects_are_excluded_by_default(self):
        public_project = PublicProjectFactory(status=Status.POSITIONING)
        _archived_project = PublicProjectFactory(status=Status.ARCHIVED)

        response = self.get(reverse("project-list"), user=None)
        self.response_ok(response)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(public_project.id))
