import random
import string

import factory

from epl.apps.project.models import Library


class LibraryFactory(factory.django.DjangoModelFactory):
    name = factory.lazy_attribute(lambda _: LibraryFactory.generate_valid_name())
    code = factory.lazy_attribute(lambda _: random.choices(string.ascii_letters + string.digits, k=10))  # noqa: S311

    class Meta:
        model = Library

    @staticmethod
    def generate_valid_name():
        # Generate a random name for the library
        return "Library_" + "".join(random.choices(string.ascii_letters + string.digits, k=8))  # noqa: S311
