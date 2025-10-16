import random

import factory


class ResourceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "project.Resource"

    code = factory.LazyAttribute(lambda o: ResourceFactory.random_string())
    title = factory.Faker("sentence", nb_words=6)
    project = factory.SubFactory("epl.apps.project.tests.factories.project.ProjectFactory")
    issn = factory.LazyAttribute(lambda _: ResourceFactory.generate_valid_issn())

    @staticmethod
    def random_string(length=12):
        import random
        import string

        chars = string.ascii_letters + string.digits
        return "".join(random.choices(chars, k=length))  # noqa: S311

    @staticmethod
    def generate_valid_issn():
        # Generate 7 random digits
        digits = [str(random.randint(0, 9)) for _ in range(7)]  # noqa: S311

        # Calculate the check digit for ISSN
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
