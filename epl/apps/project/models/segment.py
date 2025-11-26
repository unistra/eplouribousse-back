from django.db import models
from django.utils.translation import gettext as _

from epl.apps.project.models import Resource
from epl.apps.project.models.choices import SegmentType
from epl.models import UUIDPrimaryKeyField

CONTENT_NIHIL = "~~Nihil~~"


class Segment(models.Model):
    id = UUIDPrimaryKeyField()
    segment_type = models.CharField(
        choices=SegmentType.choices,
        default=SegmentType.BOUND,
        verbose_name=_("Segment type"),
    )
    content = models.TextField(_("Segment"), blank=False)
    improvable_elements = models.TextField(_("Improbable elements"), blank=True)
    exception = models.TextField(_("Exception"), blank=True)

    improved_segment = models.ForeignKey(
        "project.Segment", on_delete=models.CASCADE, related_name="improving_segments", null=True
    )

    collection = models.ForeignKey(
        "project.Collection", on_delete=models.CASCADE, related_name="segments", null=False, blank=False
    )
    order = models.PositiveSmallIntegerField(null=False, blank=False)
    retained = models.BooleanField(default=False)
    created_by = models.ForeignKey("user.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)

    _extended_permissions = ["up", "down"]

    class Meta:
        verbose_name = _("Collection segment")
        verbose_name_plural = _("Collection segments")
        constraints = [
            models.UniqueConstraint(
                fields=["collection", "order"],
                name="unique_collection_order",
                deferrable=models.Deferrable.DEFERRED,
            ),
        ]

    def __str__(self):
        return f"{self.collection.project} - {_('Segment')} n°{self.order}: {self.content}"

    @classmethod
    def get_last_order(cls, resource: Resource) -> int:
        max_order = resource.segments.aggregate(models.Max("order"))["order__max"] or 0
        return max_order + 1

    @classmethod
    def get_highest_nihil_segment_order(cls, resource: Resource) -> int:
        max_nihil_order = resource.segments.filter(content=CONTENT_NIHIL).aggregate(models.Max("order"))["order__max"]
        return max_nihil_order or 0
