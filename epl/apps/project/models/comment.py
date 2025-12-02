import textwrap

from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models
from django.utils.translation import gettext_lazy as _

from epl.models import UUIDPrimaryKeyField


class Comment(models.Model):
    id = UUIDPrimaryKeyField()
    subject = models.CharField(max_length=255, verbose_name=_("Subject"))
    content = models.TextField(verbose_name=_("Content"))
    author = models.ForeignKey("user.User", on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    content_object = GenericForeignKey("content_type", "object_id")
    object_id = models.UUIDField()
    content_type = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.CASCADE,
        null=True,
        related_name="comments",
    )

    class Meta:
        verbose_name = _("Comment")
        verbose_name_plural = _("Comments")

    def __str__(self):
        return f"{textwrap.shorten(self.subject, width=20, placeholder='…')} by {self.author} on {self.content_object}"
