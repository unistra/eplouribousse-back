from typing import TypeVar

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

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
