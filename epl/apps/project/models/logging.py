from __future__ import annotations

import typing

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.http import HttpRequest
from ipware import get_client_ip
from rest_framework.request import Request

from epl.models import UUIDPrimaryKeyField

if typing.TYPE_CHECKING:
    from epl.apps.user.models import User  # noqa: F401


class ActionLog(models.Model):
    id = UUIDPrimaryKeyField()
    action_message = models.CharField(max_length=255)
    action_time = models.DateTimeField(auto_now=True, db_index=True)
    actor = models.CharField(max_length=255)
    ip = models.GenericIPAddressField(protocol="both", unpack_ipv4=True, null=True, blank=True)

    content_object = GenericForeignKey("content_type", "object_id")
    object_id = models.UUIDField()
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)

    created_by = models.ForeignKey("user.User", on_delete=models.SET_NULL, related_name="log_entries", null=True)

    class Meta:
        verbose_name = "Log Entry"
        verbose_name_plural = "Log Entries"
        ordering = ["-action_time"]

    def __str__(self):
        return f"{self.action_time:%Y-%m-%d %H:%M:%S} - {self.action_message} by {self.actor} ({self.ip}) on {self.content_object}"

    @classmethod
    def log(
        cls, message: str, actor: User, ip: str = "", obj: models.Model = None, request: HttpRequest | Request = None
    ):
        if not ip.strip() and request:
            ip = get_client_ip(request)[0] or ""
        if len(message) > 255:
            message = message[:252] + "..."
        ActionLog.objects.create(
            action_message=message,
            actor=f"{actor.first_name} {actor.last_name} <{actor.username}>".strip(),
            ip=ip,
            content_object=obj,
            created_by=actor,
        )
