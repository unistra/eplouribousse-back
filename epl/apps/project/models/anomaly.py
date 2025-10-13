from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from epl.apps.project.models.choices import AnomalyType
from epl.models import UUIDPrimaryKeyField


class Anomaly(models.Model):
    id = UUIDPrimaryKeyField()
    segment = models.ForeignKey(
        "project.Segment",
        on_delete=models.CASCADE,
        related_name="anomalies",
    )
    resource = models.ForeignKey(
        "project.Resource",
        on_delete=models.CASCADE,
        related_name="anomalies",
    )
    type = models.CharField(max_length=100, choices=AnomalyType.choices)
    description = models.TextField(blank=True)
    fixed = models.BooleanField(default=False)
    fixed_at = models.DateTimeField(null=True, blank=True)
    fixed_by = models.ForeignKey(
        "user.User",
        on_delete=models.SET_NULL,
        related_name="fixed_anomalies",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "user.User",
        on_delete=models.SET_NULL,
        related_name="created_anomalies",
        null=True,
    )

    _extended_permissions = [
        "fix",
    ]

    class Meta:
        verbose_name = _("Anomaly")
        verbose_name_plural = _("Anomalies")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["fixed"]),
            models.Index(fields=["type"]),
        ]

    def __str__(self):
        return f"Anomaly {self.id}: {self.type}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.type == AnomalyType.OTHER and not self.description.strip():
            raise ValidationError(_("Description is required for 'Other' anomaly type."))
        elif self.type != AnomalyType.OTHER and self.description:
            self.description = ""
