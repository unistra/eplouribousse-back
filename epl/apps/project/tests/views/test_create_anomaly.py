from unittest.mock import patch

from django_tenants.urlresolvers import reverse

from epl.apps.project.models import AnomalyType, Role
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.segment import SegmentFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class CreateAnomalyTest(TestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory()
        self.library = LibraryFactory()
        self.project.libraries.add(self.library)
        self.instructor = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library)
        self.resource = ResourceFactory(project=self.project)
        self.collection = CollectionFactory(project=self.project, library=self.library, resource=self.resource)
        self.segment = SegmentFactory(collection=self.collection)

    def test_instructor_can_create_anomaly(self):
        library2 = LibraryFactory()
        self.project.libraries.add(library2)
        other_instructor = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=library2)
        payload = {
            "segment_id": str(self.segment.id),
            "type": AnomalyType.CONFUSING_WORDING,
        }
        response = self.post(
            reverse("anomaly-list"),
            data=payload,
            user=other_instructor,
        )
        self.response_created(response)
        self.assertEqual(response.data["segment"]["id"], str(self.segment.id))
        self.assertEqual(response.data["type"], AnomalyType.CONFUSING_WORDING.value)
        self.assertEqual(response.data["description"], "")
        self.assertEqual(response.data["fixed"], False)
        self.assertIsNotNone(response.data["created_at"])
        self.assertEqual(response.data["created_by"]["id"], str(other_instructor.id))

    def test_create_anomaly_checks_permission(self):
        with patch("epl.apps.project.views.anomaly.AnomalyPermissions.user_can_create_anomaly") as mock_permission:
            mock_permission.return_value = True
            payload = {
                "segment_id": str(self.segment.id),
                "type": AnomalyType.CONFUSING_WORDING,
            }
            response = self.post(
                reverse("anomaly-list"),
                data=payload,
                user=self.instructor,
            )
            self.response_created(response)
            mock_permission.assert_called_once_with(self.instructor, self.segment)

    def test_cannot_create_anomaly_without_permission(self):
        with patch("epl.apps.project.views.anomaly.AnomalyPermissions.user_can_create_anomaly") as mock_permission:
            mock_permission.return_value = False
            payload = {
                "segment_id": str(self.segment.id),
                "type": AnomalyType.CONFUSING_WORDING,
            }
            response = self.post(
                reverse("anomaly-list"),
                data=payload,
                user=self.instructor,
            )
            self.response_forbidden(response)
            mock_permission.assert_called_once_with(self.instructor, self.segment)
