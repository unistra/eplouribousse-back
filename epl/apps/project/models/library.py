from django.db import models
from django.utils.translation import gettext_lazy as _

from epl.models import UUIDPrimaryKeyField


class Library(models.Model):
    """
    Model representing a library.
    """

    id = UUIDPrimaryKeyField()
    name = models.CharField(_("Name"), max_length=255, unique=True)
    alias = models.CharField(_("Alias"), max_length=255)
    code = models.CharField(_("Code or identification"), max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Library")
        verbose_name_plural = _("Libraries")

    def __str__(self):
        return self.name
