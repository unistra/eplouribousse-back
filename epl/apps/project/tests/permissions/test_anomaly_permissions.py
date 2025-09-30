from epl.apps.project.models import Role
from epl.apps.project.permissions.anomaly import AnomalyPermissions
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.segment import SegmentFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class AnomalyPermissionTests(TestCase):
    def test_controller_can_create_anomaly(self):
        library = LibraryFactory()
        project = ProjectFactory()
        project.libraries.add(library)
        resource = ResourceFactory(project=project)
        collection = CollectionFactory(project=project, library=library, resource=resource)
        segment = SegmentFactory(collection=collection)

        controller = UserWithRoleFactory(role=Role.CONTROLLER, project=project)

        self.assertTrue(AnomalyPermissions.user_can_create_anomaly(controller, segment))

    def test_controller_in_another_project_cannot_create_anomaly(self):
        library1 = LibraryFactory()
        project1 = ProjectFactory()
        project1.libraries.add(library1)
        resource1 = ResourceFactory(project=project1)
        collection1 = CollectionFactory(project=project1, library=library1, resource=resource1)
        segment1 = SegmentFactory(collection=collection1)

        library2 = LibraryFactory()
        project2 = ProjectFactory()
        project2.libraries.add(library2)

        controller = UserWithRoleFactory(role=Role.CONTROLLER, project=project2)

        self.assertFalse(AnomalyPermissions.user_can_create_anomaly(controller, segment1))

    def test_instructor_for_library_cannot_create_anomaly(self):
        library1 = LibraryFactory()
        project1 = ProjectFactory()
        project1.libraries.add(library1)
        resource1 = ResourceFactory(project=project1)
        collection1 = CollectionFactory(project=project1, library=library1, resource=resource1)
        segment1 = SegmentFactory(collection=collection1)

        instructor = UserWithRoleFactory(role=Role.INSTRUCTOR, project=project1, library=library1)

        self.assertFalse(AnomalyPermissions.user_can_create_anomaly(instructor, segment1))

    def test_instructor_for_another_library_in_same_project_can_create_anomaly(self):
        library1 = LibraryFactory()
        library2 = LibraryFactory()

        project1 = ProjectFactory()
        project1.libraries.add(library1, library2)

        resource1 = ResourceFactory(project=project1)
        collection1 = CollectionFactory(project=project1, library=library1, resource=resource1)
        segment1 = SegmentFactory(collection=collection1)

        instructor = UserWithRoleFactory(role=Role.INSTRUCTOR, project=project1, library=library2)

        self.assertTrue(AnomalyPermissions.user_can_create_anomaly(instructor, segment1))
