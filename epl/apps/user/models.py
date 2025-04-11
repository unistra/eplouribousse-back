from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from epl.models import UUIDPrimaryKeyField


# Create your models here.
class User(AbstractUser):
    id = UUIDPrimaryKeyField()

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
