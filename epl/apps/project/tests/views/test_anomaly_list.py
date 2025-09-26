from django_tenants.urlresolvers import reverse

from epl.apps.project.models import Role
from epl.apps.project.tests.factories.anomaly import AnomalyFactory
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.segment import SegmentFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class TestAnomalyList(TestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory()
        self.library = LibraryFactory()
        self.instructor = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library)
        self.resource = ResourceFactory(project=self.project)
        self.collection = CollectionFactory(project=self.project, library=self.library, resource=self.resource)
        self.segment1 = SegmentFactory(collection=self.collection)
        self.segment2 = SegmentFactory(collection=self.collection)
        self.segment3 = SegmentFactory(collection=self.collection)

    def test_list_anomaly(self):
        _anomaly1 = AnomalyFactory(resource=self.resource, segment=self.segment1)
        _anomaly2 = AnomalyFactory(resource=self.resource, segment=self.segment1)
        response = self.get(
            reverse("anomaly-list"),
            user=self.instructor,
        )
        self.response_ok(response)
        self.assertEqual(response.data["count"], 2)

    def test_list_anomaly_filter_by_segment(self):
        _anomaly1 = AnomalyFactory(resource=self.resource, segment=self.segment1)
        _anomaly2 = AnomalyFactory(resource=self.resource, segment=self.segment2)
        response = self.get(
            reverse("anomaly-list") + f"?segment={self.segment1.id}",
            user=self.instructor,
        )
        self.response_ok(response)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(_anomaly1.id))

    def test_list_anomaly_filter_by_resource(self):
        _anomaly1 = AnomalyFactory(resource=self.resource, segment=self.segment1)
        another_resource = ResourceFactory(project=self.project)
        _anomaly2 = AnomalyFactory(resource=another_resource, segment=self.segment2)
        response = self.get(
            reverse("anomaly-list") + f"?resource={self.resource.id}",
            user=self.instructor,
        )
        self.response_ok(response)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(_anomaly1.id))

    def test_list_anomaly_filter_by_project(self):
        _anomaly1 = AnomalyFactory(resource=self.resource, segment=self.segment1)
        another_project = ProjectFactory()
        another_resource = ResourceFactory(project=another_project)
        another_collection = CollectionFactory(project=another_project, library=self.library, resource=another_resource)
        another_segment = SegmentFactory(collection=another_collection)
        _anomaly2 = AnomalyFactory(resource=another_resource, segment=another_segment)
        response = self.get(
            reverse("anomaly-list") + f"?project={self.project.id}",
            user=self.instructor,
        )
        self.response_ok(response)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(_anomaly1.id))
