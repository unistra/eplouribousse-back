from django_tenants.urlresolvers import reverse

from epl.apps.project.models import Library, Project, ProjectLibrary
from epl.apps.user.models import User
from epl.tests import TestCase


class ProjectLibraryPartialUpdateTest(TestCase):
    def test_partial_update_is_alternative_storage_site(self):
        user = User.objects.create_user(email="user@eplouribousse.fr")
        project = Project.objects.create(name="Projet Test")
        library = Library.objects.create(name="LibTest", alias="LT", code="123")
        project_library = ProjectLibrary.objects.create(
            project=project, library=library, is_alternative_storage_site=False
        )

        url = reverse("projects-library-detail", kwargs={"project_pk": project.id, "pk": library.id})
        response = self.patch(
            url, data={"is_alternative_storage_site": True}, content_type="application/json", user=user
        )

        project_library.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["is_alternative_storage_site"], True)
        self.assertTrue(project_library.is_alternative_storage_site)
