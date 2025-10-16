import factory

from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.user import UserFactory


class CollectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "project.Collection"

    resource = factory.SubFactory(ResourceFactory)
    library = factory.SubFactory(LibraryFactory)
    project = factory.SubFactory(ProjectFactory)
    created_by = factory.SubFactory(UserFactory)
    position = None
