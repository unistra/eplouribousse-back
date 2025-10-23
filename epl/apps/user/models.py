from typing import Self, TypeVar

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import IntegrityError, models
from django.utils.translation import gettext_lazy as _

from epl.apps.project.models import Library, Project, Role, UserRole
from epl.models import UUIDPrimaryKeyField

T = TypeVar("T")


class UserQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class CustomUserManager(UserManager.from_queryset(UserQuerySet)):
    use_in_migrations = True

    @staticmethod
    def _check_username_and_email(username: T, email: T) -> tuple[T, T]:
        if not email:
            raise ValueError(_("The Email must be set"))
        if not username:
            username = email
        return username, email

    def create_user(self, username=None, email=None, password=None, **extra_fields) -> "User":
        username, email = self._check_username_and_email(username, email)
        return super().create_user(username, email, password, **extra_fields)

    def create_superuser(self, username=None, email=None, password=None, **extra_fields) -> "User":
        username, email = self._check_username_and_email(username, email)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    id = UUIDPrimaryKeyField()
    email = models.EmailField(_("Email address"), unique=True)
    settings = models.JSONField(default=dict)

    objects = CustomUserManager()

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = [
            "last_name",
            "first_name",
        ]

    def __str__(self) -> str:
        name: str = f"{self.first_name} {self.last_name}".strip()
        return name or self.username

    @property
    def preferred_language(self) -> str | None:
        return self.settings.get("locale")

    @property
    def is_project_creator(self) -> bool:
        return UserRole.objects.filter(user=self, role=Role.PROJECT_CREATOR).exists()

    def is_project_admin(self, project: Project | None, search_for_any: bool = False) -> bool:
        if search_for_any:
            return UserRole.objects.filter(user=self, role=Role.PROJECT_ADMIN).exists()
        return UserRole.objects.filter(user=self, project=project, role=Role.PROJECT_ADMIN).exists()

    def is_project_manager(self, project: Project) -> bool:
        return UserRole.objects.filter(user=self, project=project, role=Role.PROJECT_MANAGER).exists()

    def is_controller(self, project: Project) -> bool:
        return UserRole.objects.filter(user=self, project=project, role=Role.CONTROLLER).exists()

    def is_instructor(self, project: Project, library: Library | str = None) -> bool:
        # library is optional so we can check if user is Instructor in the project, without needing to give a library
        queryset = UserRole.objects.filter(user=self, project=project, role=Role.INSTRUCTOR)
        if library is not None:
            filter_kwargs = {"library_id": library} if isinstance(library, str) else {"library": library}
            queryset = queryset.filter(**filter_kwargs)
        return queryset.exists()

    def is_guest(self, project: Project) -> bool:
        return UserRole.objects.filter(user=self, project=project, role=Role.GUEST).exists()

    def set_is_project_creator(self, value: bool, assigned_by: Self) -> None:
        if value:
            try:
                UserRole.objects.create(user=self, role=Role.PROJECT_CREATOR, project=None, assigned_by=assigned_by)
            except IntegrityError:
                pass  # Role already exists
        else:
            UserRole.objects.filter(user=self, role=Role.PROJECT_CREATOR).delete()
