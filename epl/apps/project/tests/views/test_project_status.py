from django_tenants.urlresolvers import reverse

from epl.apps.project.models import Project, Status
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import UserFactory
from epl.tests import TestCase


class ProjectStatusListTest(TestCase):
    def test_list_available_statuses(self):
        response = self.get(reverse("project-list-statuses"))
        self.response_ok(response)
        self.assertListEqual(
            [_s["status"] for _s in response.data],
            [_s[0] for _s in Status.choices],
        )


class UpdateProjectStatusTest(TestCase):
    def test_update_project_status(self):
        user = UserFactory()
        project: Project = ProjectFactory(status=Status.DRAFT)
        response = self.patch(
            reverse("project-update-status", kwargs={"pk": project.id}),
            data={"status": Status.READY},
            content_type="application/json",
            user=user,
        )
        self.response_ok(response)
        project.refresh_from_db()
        self.assertEqual(project.status, Status.READY)

    def test_update_project_status_invalid(self):
        user = UserFactory()
        project: Project = ProjectFactory(status=Status.DRAFT)
        response = self.patch(
            reverse("project-update-status", kwargs={"pk": project.id}),
            data={"status": 300},
            content_type="application/json",
            user=user,
        )
        self.response_bad_request(response)
