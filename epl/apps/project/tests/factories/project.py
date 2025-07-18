import factory
from django.utils.timezone import now

from epl.apps.project.models import Status


class ProjectFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("company")

    class Meta:
        model = "project.Project"


class PrivateProjectFactory(ProjectFactory):
    is_private = True

    class Meta:
        model = "project.Project"


class PublicProjectFactory(ProjectFactory):
    is_private = False
    status = Status.POSITIONING
    active_after = now()

    class Meta:
        model = "project.Project"


class PositioningProjectFactory(ProjectFactory):
    status = Status.POSITIONING
    active_after = now()

    class Meta:
        model = "project.Project"
