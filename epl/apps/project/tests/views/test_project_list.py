from django_tenants.urlresolvers import reverse
from parameterized import parameterized

from epl.apps.project.models import ProjectStatus, Role, UserRole
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import (
    PrivateLaunchedProjectFactory,
    PrivateProjectFactory,
    PublicLaunchedInFutureProjectFactory,
    PublicLaunchedProjectFactory,
    PublicProjectFactory,
)
from epl.apps.project.tests.factories.user import ProjectCreatorFactory, UserFactory, UserWithRoleFactory
from epl.tests import TestCase


class ProjectListTest(TestCase):
    @parameterized.expand(
        [
            (Role.PROJECT_CREATOR, 200),
            (Role.INSTRUCTOR, 200),
            (Role.PROJECT_ADMIN, 200),
            (Role.PROJECT_MANAGER, 200),
            (Role.CONTROLLER, 200),
            (Role.GUEST, 200),
            (None, 200),
        ]
    )
    def test_view_public_project(self, role, expected_status):
        project_public_launched1 = PublicLaunchedProjectFactory()
        project_public_launched2 = PublicLaunchedProjectFactory()
        library = LibraryFactory()
        user = UserWithRoleFactory(role=role, project=project_public_launched1, library=library)

        response = self.get(reverse("project-list"), user=user)

        self.assertEqual(response.status_code, expected_status)
        self.assertListEqual(
            sorted([project["id"] for project in response.data["results"]]),
            sorted([str(project_public_launched1.id), str(project_public_launched2.id)]),
        )
        self.assertEqual(response.data["count"], 2)

    @parameterized.expand(
        [
            Role.INSTRUCTOR,
            Role.PROJECT_ADMIN,
            Role.PROJECT_MANAGER,
            Role.CONTROLLER,
            Role.GUEST,
        ]
    )
    def test_view_private_launched_project(self, role):
        _project_private_launched = PrivateLaunchedProjectFactory()
        his_project_private_launched = PrivateLaunchedProjectFactory()
        library = LibraryFactory()
        user = UserWithRoleFactory(role=role, project=his_project_private_launched, library=library)

        response = self.get(reverse("project-list"), user=user)

        self.assertListEqual(
            sorted([project["id"] for project in response.data["results"]]),
            sorted([str(his_project_private_launched.id)]),
        )
        self.assertEqual(response.data["count"], 1)

    def test_project_creator_see_all_projects(self):
        project_public_launched = PublicLaunchedProjectFactory()
        project_public_not_launched = PublicProjectFactory(status=ProjectStatus.DRAFT)
        project_private_launched = PrivateLaunchedProjectFactory()
        project_private_not_launched = PrivateProjectFactory(status=ProjectStatus.DRAFT)

        user = UserWithRoleFactory(role=Role.PROJECT_CREATOR)

        response = self.get(reverse("project-list"), user=user)
        self.response_ok(response)
        self.assertListEqual(
            sorted([project["id"] for project in response.data["results"]]),
            sorted(
                [
                    str(project_public_launched.id),
                    str(project_public_not_launched.id),
                    str(project_private_launched.id),
                    str(project_private_not_launched.id),
                ]
            ),
        )
        self.assertEqual(response.data["count"], 4)

    def test_anonymous_user_see_only_public_and_launched_projects(self):
        project_public_launched1 = PublicLaunchedProjectFactory()
        project_public_launched2 = PublicLaunchedProjectFactory()
        _project_public_not_launched = PublicLaunchedInFutureProjectFactory()
        _project_private_launched = PrivateLaunchedProjectFactory()

        response = self.get(reverse("project-list"), user=None)
        self.response_ok(response)
        self.assertListEqual(
            sorted([project["id"] for project in response.data["results"]]),
            sorted([str(project_public_launched1.id), str(project_public_launched2.id)]),
        )
        self.assertEqual(response.data["count"], 2)

    @parameterized.expand(
        [
            Role.INSTRUCTOR,
            Role.CONTROLLER,
            Role.GUEST,
        ]
    )
    def test_participant_see_only_public_launched_and_his_projects(self, role):
        project_public_launched1 = PublicLaunchedProjectFactory()
        project_public_launched2 = PublicLaunchedProjectFactory()
        his_project_private_launched = PrivateLaunchedProjectFactory()
        his_project_public_not_launched = PublicProjectFactory(status=ProjectStatus.READY)
        library = LibraryFactory()

        user = UserWithRoleFactory(role=role, project=his_project_private_launched, library=library)
        UserRole.objects.create(user=user, role=role, project=his_project_public_not_launched, library=library)

        response = self.get(reverse("project-list"), user=user)
        self.response_ok(response)

        self.assertListEqual(
            sorted([project["id"] for project in response.data["results"]]),
            sorted(
                [
                    str(project_public_launched1.id),
                    str(project_public_launched2.id),
                    str(his_project_private_launched.id),
                ]
            ),
        )
        self.assertEqual(response.data["count"], 3)

    def test_archived_projects_are_excluded_by_default(self):
        public_project = PublicProjectFactory(status=ProjectStatus.LAUNCHED)
        _archived_project = PublicProjectFactory(status=ProjectStatus.ARCHIVED)

        response = self.get(reverse("project-list"), user=None)
        self.response_ok(response)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(public_project.id))


class ProjectListFilterTest(TestCase):
    def test_status_filter(self):
        user = ProjectCreatorFactory()
        public_project = PublicProjectFactory(status=ProjectStatus.LAUNCHED)
        _draft_project = PublicProjectFactory(status=ProjectStatus.DRAFT)
        _archived_project = PublicProjectFactory(status=ProjectStatus.ARCHIVED)

        response = self.get(f"{reverse('project-list')}?status={ProjectStatus.LAUNCHED}", user=user)
        self.response_ok(response)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(public_project.id))

    def test_filter_participating_in_project(self):
        user = UserFactory()
        _public_project = PublicLaunchedProjectFactory()
        guest_project = PublicLaunchedProjectFactory()
        private_project = PublicLaunchedProjectFactory()
        UserRole.objects.create(user=user, project=guest_project, role=Role.GUEST, assigned_by=user)
        UserRole.objects.create(user=user, project=private_project, role=Role.INSTRUCTOR, assigned_by=user)

        response = self.get(f"{reverse('project-list')}?participant=true", user=user)
        self.response_ok(response)
        self.assertEqual(response.data["count"], 2)
        self.assertListEqual(
            sorted([project["id"] for project in response.data["results"]]),
            sorted([str(guest_project.id), str(private_project.id)]),
        )

    def test_library_is_in_project_filter(self):
        user = UserFactory()
        public_project = PublicLaunchedProjectFactory()
        _other_project = PublicLaunchedProjectFactory()
        library = LibraryFactory()
        public_project.libraries.add(library)

        response = self.get(f"{reverse('project-list')}?library={library.id}", user=user)
        self.response_ok(response)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(public_project.id))
