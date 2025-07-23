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


class UserWithRoleFactory:
    def __init__(self, project=None, library=None):
        self.project = project
        self.library = library

    def create_with_role(self, role, project=None, library=None):
        user = UserFactory()
        target_project = project or self.project  # Si aucun projet n'est fourni, utilise celui de l'instance
        target_library = library or self.library

        if role == Role.PROJECT_CREATOR:
            user.set_is_project_creator(True, assigned_by=user)
        elif role == Role.GUEST:
            UserRole.objects.create(
                user=user,
                project=None,
                role=role,
                assigned_by=user,
            )
        elif role in [Role.PROJECT_ADMIN, Role.PROJECT_MANAGER, Role.CONTROLLER]:
            if not target_project:
                raise ValueError(f"Rôle {role} nécessite un projet")
            UserRole.objects.create(
                user=user,
                project=target_project,
                role=role,
                assigned_by=user,
            )
        elif role in [Role.INSTRUCTOR]:
            if not target_project or not target_library:
                raise ValueError(f"Rôle {role} nécessite projet ET bibliothèque")
            UserRole.objects.create(
                user=user,
                project=target_project,
                library=target_library,
                role=role,
                assigned_by=user,
            )

        return user

    def create_project_creator(self):
        return self.create_with_role(Role.PROJECT_CREATOR)

    def create_project_admin(self):
        return self.create_with_role(Role.PROJECT_ADMIN, project=self.project)

    def create_project_manager(self):
        return self.create_with_role(Role.PROJECT_MANAGER, project=self.project)

    def create_instructor(self):
        return self.create_with_role(Role.INSTRUCTOR, project=self.project, library=self.library)

    def create_controller(self):
        return self.create_with_role(Role.CONTROLLER, project=self.project)

    def create_guest(self):
        return self.create_with_role(Role.GUEST)
