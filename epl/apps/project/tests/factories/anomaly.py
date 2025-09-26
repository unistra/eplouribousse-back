import factory

from epl.apps.project.models import AnomalyType
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.segment import SegmentFactory
from epl.apps.project.tests.factories.user import UserFactory


class AnomalyFactory(factory.django.DjangoModelFactory):
    segment = factory.SubFactory(SegmentFactory)
    resource = factory.SubFactory(ResourceFactory)
    fixed_by = factory.SubFactory(UserFactory)
    created_by = factory.SubFactory(UserFactory)
    type = factory.Iterator([choice[0] for choice in AnomalyType.choices if choice[0] != AnomalyType.OTHER.value])

    class Meta:
        model = "project.Anomaly"
