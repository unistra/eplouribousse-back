from __future__ import annotations

from django.db import models
from django.utils.translation import gettext as _


class AlertType(models.TextChoices):
    POSITIONING = "positioning", _("Positioning")
    ARBITRATION = "arbitration", _("Arbitration")
    INSTRUCTION = "instruction", _("Instruction")
    CONTROL = "control", _("Control")
    EDITION = "edition", _("Edition")
    PRESERVATION = "preservation", _("Preservation")
    TRANSFER = "transfer", _("Transfer")


class AnomalyType(models.TextChoices):
    PUB_PERIOD_PASSED = "pub_period_passed", _("Publication Period Passed")
    DISCONTINUOUS = "discontinuous_segment", _("Discontinuous Segment")
    EXCP_IMPROVABLE = "excp_improvable", _("Exception or improvable (off-segment)")
    CHRONOLOGICAL_ERROR = "chronological_error", _("Chronological Error")
    SEGMENT_OVERLAP = "segment_overlap", _("Overlap Segment")
    MISUSE_OF_REMEDIATED_LIB = "misuse_of_remediated_library", _("Improper use of remediated library")
    CONFUSING_WORDING = "confusing_wording", _("Confusing wording")
    OTHER = "other", _("Other")


class ProjectStatus(models.IntegerChoices):
    DRAFT = 10, _("Draft")
    REVIEW = 20, _("Review")
    READY = 30, _("Ready")
    LAUNCHED = 40, _("Launched")
    ARCHIVED = 100, _("Archived")


class ResourceStatus(models.IntegerChoices):
    POSITIONING = 10, _("Positioning")
    INSTRUCTION_BOUND = 20, _("Instruction Bound Copies")
    ANOMALY_BOUND = 25, _("Anomaly Bound Copies")
    CONTROL_BOUND = 30, _("Control Bound Copies")
    INSTRUCTION_UNBOUND = 40, _("Instruction Unbound Copies")
    ANOMALY_UNBOUND = 45, _("Anomaly Unbound Copies")
    CONTROL_UNBOUND = 50, _("Control Unbound Copies")
    EDITION = 60, _("Edition")


class SegmentType(models.TextChoices):
    BOUND = "bound", _("Bound")
    UNBOUND = "unbound", _("Unbound")
