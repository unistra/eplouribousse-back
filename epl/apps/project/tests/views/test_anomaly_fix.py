from django_tenants.urlresolvers import reverse

from epl.apps.project.models import AnomalyType, Role
from epl.apps.project.tests.factories.anomaly import AnomalyFactory
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.segment import SegmentFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class FixAnomalyTest(TestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory()
        self.library = LibraryFactory()
        self.instructor = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library)
        self.resource = ResourceFactory(project=self.project)
        self.collection = CollectionFactory(project=self.project, library=self.library, resource=self.resource)
        self.segment1 = SegmentFactory(collection=self.collection)

        self.anomaly = AnomalyFactory(
            segment=self.segment1,
            resource=self.resource,
            created_by=self.instructor,
            type=AnomalyType.DISCONTINUOUS,
        )

    def test_anonymous_user_cannot_fix_anomaly(self):
        response = self.patch(
            reverse("anomaly-fix", kwargs={"pk": self.anomaly.id}),
            user=None,
        )
        self.response_unauthorized(response)

    def test_instructor_can_fix_anomaly(self):
        response = self.patch(
            reverse("anomaly-fix", kwargs={"pk": self.anomaly.id}),
            user=self.instructor,
        )
        self.response_ok(response)
        self.anomaly.refresh_from_db()
        self.assertTrue(self.anomaly.fixed)
        self.assertEqual(str(self.anomaly.fixed_by.id), str(self.instructor.id))

    def test_admin_can_fix_anomaly(self):
        admin = UserWithRoleFactory(role=Role.PROJECT_ADMIN, project=self.project)
        response = self.patch(
            reverse("anomaly-fix", kwargs={"pk": self.anomaly.id}),
            user=admin,
        )
        self.response_ok(response)
        self.anomaly.refresh_from_db()
        self.assertTrue(self.anomaly.fixed)
        self.assertEqual(str(self.anomaly.fixed_by.id), str(admin.id))
