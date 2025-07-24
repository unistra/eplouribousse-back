from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.utils.translation import gettext as _

from epl.apps.project.models.choices import ResourceStatus
from epl.apps.project.models.comment import Comment
from epl.models import UUIDPrimaryKeyField
from epl.validators import IssnValidator


def default_instuction_turns():
    return {
        "bound_copies": {
            "turns": [],
        },
        "unbound_copies": {
            "turns": [],
        },
    }


class Arbitration(models.IntegerChoices):
    ZERO = 0, _("Arbitration Type 0")
    ONE = 1, _("Arbitration Type 1")
    NONE = 2, _("No arbitration")


class Resource(models.Model):
    id = UUIDPrimaryKeyField()
    code = models.CharField(_("Code (PPN or other)"), max_length=25, db_index=True)  # PPN
    title = models.CharField(_("Title"), max_length=510, db_index=True)
    project = models.ForeignKey("Project", on_delete=models.CASCADE, related_name="resources")
    status = models.IntegerField(_("Status"), choices=ResourceStatus.choices, default=ResourceStatus.POSITIONING)
    instruction_turns = models.JSONField(_("Instruction turns"), default=default_instuction_turns, blank=True)
    arbitration = models.IntegerField(
        _("Arbitration"), choices=Arbitration.choices, default=Arbitration.NONE, db_index=True
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    comments = GenericRelation(Comment)

    _extended_permissions = [
        "list_statuses",
    ]

    class Meta:
        verbose_name = _("Resource")
        verbose_name_plural = _("Resources")
        ordering = ["code", "project"]
        constraints = [
            models.UniqueConstraint(fields=["code", "project"], name="unique_resource_code_per_project"),
        ]

    def __str__(self):
        return f"{self.code} - {self.project_id}"

    @property
    def next_turn(self) -> str:
        if self.status == ResourceStatus.INSTRUCTION_BOUND:
            return self.instruction_turns.get("bound_copies", {}).get("turns", [])[0]
        elif self.status == ResourceStatus.INSTRUCTION_UNBOUND:
            return self.instruction_turns.get("unbound_copies", {}).get("turns", [])[0]
        return ""


class Collection(models.Model):
    id = UUIDPrimaryKeyField()
    resource = models.ForeignKey("Resource", on_delete=models.CASCADE, related_name="collections")  # RCR
    library = models.ForeignKey("Library", on_delete=models.CASCADE, related_name="collections")  # RCR
    project = models.ForeignKey("Project", on_delete=models.CASCADE, related_name="collections")
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
    is_result_collection = models.BooleanField(
        _("Is the result collection"),
        default=False,
        db_index=True,
        help_text=_("The collection is the result of a deduplication process"),
    )
    comments = GenericRelation(Comment)

    class Meta:
        verbose_name = _("Collection")
        verbose_name_plural = _("Collections")
        ordering = ["resource__title"]

    def __str__(self):
        return f"{self.id}"

    def save(self, *args, **kwargs):
        if self.position is not None and self.position != 0:
            self.exclusion_reason = ""
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def is_excluded(self):
        return self.position == 0
