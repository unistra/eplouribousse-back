from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context
from parameterized import parameterized

from epl.apps.project.models import ProjectLibrary, Role
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class ProjectLibraryPatchPermissionTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.project = ProjectFactory()
            self.library = LibraryFactory()
            self.project_library = ProjectLibrary.objects.create(
                project=self.project, library=self.library, is_alternative_storage_site=False
            )

    @parameterized.expand(
        [
            (Role.TENANT_SUPER_USER, False, 403),
            (Role.PROJECT_CREATOR, True, 200),
            (Role.PROJECT_ADMIN, True, 200),
            (Role.INSTRUCTOR, False, 403),
            (Role.PROJECT_MANAGER, False, 403),
            (Role.CONTROLLER, False, 403),
            (Role.GUEST, False, 403),
            (None, False, 403),  # Anonymous user
        ]
    )
    def test_patch_project_library_permissions(self, role, should_succeed, expected_status_code):
        user = UserWithRoleFactory(role=role, project=self.project, library=self.library)
        url = reverse("projects-library-detail", kwargs={"project_pk": self.project.id, "pk": self.library.id})
        response = self.patch(
            url, data={"is_alternative_storage_site": True}, content_type="application/json", user=user
        )
        self.assertEqual(response.status_code, expected_status_code)
        self.project_library.refresh_from_db()
        if should_succeed:
            self.assertTrue(response.data["is_alternative_storage_site"])
        else:
            self.assertFalse(self.project_library.is_alternative_storage_site)
