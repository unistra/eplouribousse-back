import factory


class UserFactory(factory.django.DjangoModelFactory):
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    email = factory.Faker("email")

    class Meta:
        model = "user.User"
        skip_postgeneration_save = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """
        Override the _create method to handle the creation of the user instance.
        """
        manager = cls._get_manager(model_class)
        user = manager.create_user(*args, **kwargs)
        return user
