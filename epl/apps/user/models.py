from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from epl.models import UUIDPrimaryKeyField


class User(AbstractUser):
    id = UUIDPrimaryKeyField()
    email = models.EmailField(_("Email address"), unique=True)

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self) -> str:
        name: str = f"{self.first_name} {self.last_name}".strip()
        return name or self.username
