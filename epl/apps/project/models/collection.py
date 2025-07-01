from django.db import models
from django.utils.translation import gettext_lazy as _

from epl.models import UUIDPrimaryKeyField
from epl.validators import IssnValidator


class Collection(models.Model):
    id = UUIDPrimaryKeyField()
    title = models.CharField(_("Title"), max_length=510, db_index=True)
    code = models.CharField(_("Code (PPN or other)"), max_length=25, db_index=True)  # PPN
    library = models.ForeignKey("Library", on_delete=models.CASCADE)  # RCR
    project = models.ForeignKey("Project", on_delete=models.CASCADE)
    issn = models.CharField(_("ISSN"), max_length=9, blank=True, validators=[IssnValidator()])
    call_number = models.CharField(_("Call number"), blank=True)  # Cote
    hold_statement = models.CharField(_("Hold statement"), blank=True)  # État de la collection
    missing = models.CharField(_("Missing"), blank=True)  # Lacunes
    publication_history = models.CharField(
        _("Publication history"), blank=True
    )  # Historique de la publication (todo absent des exemples)
    numbering = models.CharField(_("Numbering"), blank=True)  # Numérotation (todo absent des exemples)
    notes = models.TextField(_("Notes"), blank=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    created_by = models.ForeignKey("user.User", on_delete=models.SET_NULL, null=True, verbose_name=_("Created by"))

    alias = models.CharField(
        "Alias", max_length=255, blank=True, help_text=_("Alias for a duplicate collection in the same library")
    )
    position = models.IntegerField("Position", null=True, blank=True, help_text=_("Positioning rank of a collection"))
    exclusion_reason = models.CharField(
        "Exclusion reason",
        max_length=255,
        blank=True,
        help_text=_("Reason for excluding the collection from deduplication"),
    )
    positioning_comment = models.TextField(
        "Positioning comment", blank=True, help_text=_("Instructor's comment on the collection positioning")
    )

    class Meta:
        verbose_name = _("Collection")
        verbose_name_plural = _("Collections")
        ordering = ["title"]

    def __str__(self):
        return f"{self.code} - {self.title}"

    def save(self, *args, **kwargs):
        if self.position is not None and self.position != 0:
            self.exclusion_reason = ""
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def is_excluded(self):
        return self.position == 0

    @is_excluded.setter
    def is_excluded(self, value):
        if value:
            self.position = 0
