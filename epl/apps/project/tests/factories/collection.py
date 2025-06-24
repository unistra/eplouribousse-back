import random
import string

import factory

from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.user import UserFactory


class CollectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "project.Collection"

    title = factory.Faker("sentence", nb_words=6)
    code = factory.LazyAttribute(lambda _: "".join(random.choices(string.ascii_letters + string.digits, k=10)))  # noqa: S311
    library = factory.SubFactory(LibraryFactory)
    project = factory.SubFactory(ProjectFactory)
    issn = factory.LazyAttribute(lambda _: CollectionFactory.generate_valid_issn())
    created_by = factory.SubFactory(UserFactory)
    position = None

    @staticmethod
    def generate_valid_issn():
        # Generate 7 random digits
        digits = [str(random.randint(0, 9)) for _ in range(7)]  # noqa: S311

        # Caclulate the check digit for ISSN
        check_digit = 0
        for i in range(7):
            check_digit += int(digits[i]) * (8 - i)
        check_digit = 11 - (check_digit % 11)
        if check_digit == 10:
            check_digit = "X"
        elif check_digit == 11:
            check_digit = 0

        issn = "".join(digits) + str(check_digit)
        return f"{issn[:4]}-{issn[4:]}"
