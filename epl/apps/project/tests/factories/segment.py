import factory

from epl.apps.project.models import Role, Segment
from epl.apps.project.models.choices import SegmentType
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory


class SegmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "project.Segment"

    segment_type = SegmentType.BOUND
    content = factory.Faker("text")
    improvable_elements = factory.Faker("text")
    exception = factory.Faker("text")
    collection = factory.SubFactory(CollectionFactory)
    order = factory.LazyAttribute(lambda o: Segment.get_last_order(resource=o.collection.resource))
    retained = False
    created_by = factory.LazyAttribute(
        lambda o: UserWithRoleFactory(role=Role.INSTRUCTOR, project=o.collection.project, library=o.collection.library)
    )
    created_at = factory.Faker("date_time_this_year")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        collection = kwargs.pop("collection", None)
        if collection is not None:
            kwargs["collection"] = collection
        return super()._create(model_class, *args, **kwargs)
