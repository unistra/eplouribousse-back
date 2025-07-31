from datetime import timedelta

import factory
from django.utils.timezone import now

from epl.apps.project.models import ProjectStatus

MODEL = "project.Project"


class ProjectFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("company")
    description = factory.Faker("sentence")

    class Meta:
        model = MODEL


class PrivateProjectFactory(ProjectFactory):
    is_private = True

    class Meta:
        model = MODEL


class PrivateLaunchedProjectFactory(PrivateProjectFactory):
    status = ProjectStatus.LAUNCHED
    active_after = now()

    class Meta:
        model = MODEL


class PublicProjectFactory(ProjectFactory):
    is_private = False

    class Meta:
        model = MODEL


class PublicLaunchedProjectFactory(PublicProjectFactory):
    status = ProjectStatus.LAUNCHED
    active_after = now()

    class Meta:
        model = MODEL


class PublicLaunchedInFutureProjectFactory(PublicLaunchedProjectFactory):
    active_after = now() + timedelta(days=1)

    class Meta:
        model = MODEL


class PositioningProjectFactory(ProjectFactory):
    status = ProjectStatus.LAUNCHED
    active_after = now()

    class Meta:
        model = MODEL


class LaunchedProjectFactory(PublicProjectFactory):
    active_after = now() - timedelta(days=1)

    class Meta:
        model = MODEL
