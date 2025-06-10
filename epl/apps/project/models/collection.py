from django.db import models
from django.utils.translation import gettext_lazy as _

from epl.apps.project.models.library import Library
from epl.models import UUIDPrimaryKeyField


class Collection(models):
    id = UUIDPrimaryKeyField()
    title = models.CharField(_("Title"), max_length=255, db_index=True)
    code = models.CharField(_("Code (PPN or other)"), max_length=25)  # PPN
    library = models.ForeignKey(Library, on_delete=models.CASCADE)  # RCR
    extra = models.IntegerField(_("Extra copy"), default=0)  # Serial for extra copies
    issn = models.CharField(_("ISSN"), max_length=9, blank=True)
    call_number = models.CharField(_("Call number"), blank=True)  # Cote
    hold_statement = models.CharField(_("Hold statement"), blank=True)  # État de la collection
    missing = models.CharField(_("Missing"), blank=True)  # Lacunes
    publication_history = models.CharField(
        _("Publication history"), blank=True
    )  # Historique de la publication (todo absent des exemples)
    numbering = models.CharField(_("Numbering"), blank=True)  # Numérotation (todo absent des exemples)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["code", "library", "extra"],
                name="%(app_label)s_%(class)s_unique_extra",
            )
        ]
