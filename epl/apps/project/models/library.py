from django.db import models

from epl.models import UUIDPrimaryKeyField


class Library(models.Model):
    """
    Model representing a library.
    """

    id = UUIDPrimaryKeyField()
    name = models.CharField(max_length=255, unique=True)
    alias = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Library"
        verbose_name_plural = "Libraries"

    def __str__(self):
        return self.name
