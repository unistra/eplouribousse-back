from datetime import timedelta

import factory
from django.utils.timezone import now

from epl.apps.project.models import ProjectStatus


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
    status = ProjectStatus.LAUNCHED
    active_after = now()

    class Meta:
        model = "project.Project"


class PositioningProjectFactory(ProjectFactory):
    status = ProjectStatus.LAUNCHED
    active_after = now()

    class Meta:
        model = "project.Project"


class LaunchedProjectFactory(PublicProjectFactory):
    active_after = now() - timedelta(days=1)

    class Meta:
        model = "project.Project"
