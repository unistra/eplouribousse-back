import factory

from epl.apps.project.models import Role, UserRole


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


class ProjectCreatorFactory(UserFactory):
    """
    Factory for creating a user with the PROJECT_CREATOR role.
    """

    @factory.post_generation
    def project_creator(self, create, extracted, **kwargs):
        if create:
            self.set_is_project_creator(True, assigned_by=self)


class UserWithRoleFactory(factory.django.DjangoModelFactory):
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    email = factory.Faker("email")

    class Meta:
        model = "user.User"
        skip_postgeneration_save = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        role = kwargs.pop("role", None)
        project = kwargs.pop("project", None)
        library = kwargs.pop("library", None)

        manager = cls._get_manager(model_class)
        user = manager.create_user(*args, **kwargs)

        match role:
            case Role.PROJECT_CREATOR:
                user.set_is_project_creator(True, assigned_by=user)
            case Role.INSTRUCTOR:
                if not project or not library:
                    raise ValueError(f"Role {role} requires project AND library")
                UserRole.objects.create(
                    user=user,
                    project=project,
                    library=library,
                    role=role,
                    assigned_by=user,
                )
            case Role.PROJECT_ADMIN | Role.PROJECT_MANAGER | Role.CONTROLLER | Role.GUEST:
                if not project:
                    raise ValueError(f"Role {role} requires a project")
                UserRole.objects.create(
                    user=user,
                    project=project,
                    role=role,
                    assigned_by=user,
                )

        return user
