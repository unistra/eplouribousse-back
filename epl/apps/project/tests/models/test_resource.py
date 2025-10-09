from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.tests import TestCase


class ResourceTurnsTest(TestCase):
    def setUp(self):
        self.project = ProjectFactory()
        self.library_1 = LibraryFactory()
        self.library_2 = LibraryFactory()
        self.project.libraries.add(self.library_1, self.library_2)
        self.resource = ResourceFactory(project=self.project)

        self.collection_1 = CollectionFactory(resource=self.resource, library=self.library_1, position=1)
        self.collection_2 = CollectionFactory(resource=self.resource, library=self.library_2, position=2)
        self.collection_3 = CollectionFactory(resource=self.resource, library=self.library_1, position=4)
        self.excluded_collection = CollectionFactory(resource=self.resource, library=self.library_1, position=0)

    def test_calculate_turns(self):
        turns = self.resource.calculate_turns()
        expected_turns = [
            {"library": str(self.library_1.id), "collection": str(self.collection_1.id)},
            {"library": str(self.library_2.id), "collection": str(self.collection_2.id)},
            {"library": str(self.library_1.id), "collection": str(self.collection_3.id)},
        ]
        self.assertEqual(turns, expected_turns)
