import random
import string

import factory

from epl.apps.project.models import Library


class LibraryFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("company")
    code = factory.lazy_attribute(lambda _: random.choices(string.ascii_letters + string.digits, k=10))  # noqa: S311

    class Meta:
        model = Library
