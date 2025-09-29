from __future__ import annotations

from django.db import models
from django.utils.translation import gettext as _


class ProjectStatus(models.IntegerChoices):
    DRAFT = 10, _("Draft")
    REVIEW = 20, _("Review")
    READY = 30, _("Ready")
    LAUNCHED = 40, _("Launched")
    ARCHIVED = 100, _("Archived")


class ResourceStatus(models.IntegerChoices):
    POSITIONING = 10, _("Positioning")
    INSTRUCTION_BOUND = 20, _("Instruction Bound Copies")
    CONTROL_BOUND = 30, _("Control Bound Copies")
    INSTRUCTION_UNBOUND = 40, _("Instruction Unbound Copies")
    CONTROL_UNBOUND = 50, _("Control Unbound Copies")
    EDITION = 60, _("Edition")


class SegmentType(models.TextChoices):
    BOUND = "bound", _("Bound")
    UNBOUND = "unbound", _("Unbound")


class AlertType(models.TextChoices):
    POSITIONING = "position", _("Position")
    ARBITRATION = "arbitration", _("Arbitration")
    INSTRUCTION = "instruction", _("Instruction")
    CONTROL = "control", _("Control")
    EDITION = "edition", _("Edition")
    CONSERVATION = "conservation", _("Conservation")
    TRANSFER = "transfer", _("Transfer")
