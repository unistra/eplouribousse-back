import factory


class ResourceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "project.Resource"

    code = factory.LazyAttribute(lambda o: ResourceFactory.random_string())
    title = factory.Faker("sentence", nb_words=6)
    project = factory.SubFactory("epl.apps.project.tests.factories.project.ProjectFactory")

    @staticmethod
    def random_string(length=12):
        import random
        import string

        chars = string.ascii_letters + string.digits
        return "".join(random.choices(chars, k=length))  # noqa: S311
