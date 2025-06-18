import factory


class ProjectFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("company")

    class Meta:
        model = "project.Project"
