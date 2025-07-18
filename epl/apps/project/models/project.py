from __future__ import annotations

import typing

from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from epl.models import UUIDPrimaryKeyField

if typing.TYPE_CHECKING:
    from epl.apps.user.models import User


DEFAULT_EXCLUSION_REASONS = [
    _lazy("Participation in another project"),
    _lazy("Incorrect assignment"),
    _lazy("Other"),
]


class Status(models.IntegerChoices):
    DRAFT = 10, _("Draft")
    REVIEW = 20, _("Review")
    READY = 30, _("Ready")
    POSITIONING = 40, _("Positioning")
    INSTRUCTION_BOUND = 50, _("Instruction Bound Copies")
    INSTRUCTION_UNBOUND = 60, _("Instruction Unbound Copies")
    ARCHIVED = 100, _("Archived")


class ProjectQuerySet(models.QuerySet):
    def public_or_participant(self, user: User = None) -> models.QuerySet[Project]:
        if not user or not user.is_authenticated:
            return self.public()

        if user.is_superuser or user.is_project_creator:
            return self.all()

        return self.public() | self.participating(user)

    def participating(self, user: User = None) -> models.QuerySet[Project]:
        if not user or not user.is_authenticated:
            return self.none()

        # Si le project n'est pas lancé, seuls les admin, manager peuvent le voir
        # Pour les autres roles, il faut que le projet soit lancé.
        return self.filter(
            models.Q(user_roles__user=user, user_roles__role__in=[Role.PROJECT_ADMIN, Role.PROJECT_MANAGER])
            | models.Q(
                user_roles__user=user,
                user_roles__role__in=[Role.INSTRUCTOR, Role.CONTROLLER, Role.GUEST],
                status__gte=Status.POSITIONING,
                active_after__lte=now(),
            )
        )

    def participant(self, user: User) -> models.QuerySet[Project]:
        """
        Returns projects where the user has a role.
        """
        return self.filter(user_roles__user=user)

    def public(self) -> models.QuerySet[Project]:
        return self.filter(is_private=False, status__gte=Status.POSITIONING, active_after__lte=now())

    def not_archived(self):
        return self.filter(status__lt=Status.ARCHIVED)

    def archived(self):
        return self.filter(status__gte=Status.ARCHIVED)

    def status(self, status: int) -> models.QuerySet[Project]:
        return self.filter(status=status)


class Project(models.Model):
    id = UUIDPrimaryKeyField()
    name = models.CharField(_("Name"), max_length=255)
    description = models.TextField(_("Description"), blank=True)
    libraries = models.ManyToManyField("Library", through="ProjectLibrary")
    is_private = models.BooleanField(_("Is private"), default=False)
    active_after = models.DateTimeField(_("Active after"), default=now)
    status = models.IntegerField(_("Status"), choices=Status.choices, default=Status.DRAFT)
    settings = models.JSONField(_("Settings"), default=dict)
    invitations = models.JSONField(_("Invitations"), default=list, blank=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    _extended_permissions = [
        "add_library",
        "update_status",
        "exclusion_reason",
        "remove_exclusion_reason",
        "status",
    ]

    objects = ProjectQuerySet.as_manager()

    class Meta:
        verbose_name = _("Project")
        verbose_name_plural = _("Projects")
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(status__in=[choice[0] for choice in Status.choices]),
                name="%(app_label)s_%(class)s_status_valid",
            ),
        ]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        self.libraries.clear()
        super().delete(*args, **kwargs)

    @property
    def exclusion_reasons(self):
        return self.settings.get("exclusion_reasons", [])


class ProjectLibrary(models.Model):
    project = models.ForeignKey("Project", on_delete=models.CASCADE)
    library = models.ForeignKey("Library", on_delete=models.CASCADE)
    is_alternative_storage_site = models.BooleanField(_("Is alternative storage site"), default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["project", "library"], name="unique_project_library")]

    def __str__(self):
        alternative_storage_site = _("Alternative storage site")
        return f"{self.project.name} - {self.library.name} {alternative_storage_site if self.is_alternative_storage_site else ''}"


class Role(models.TextChoices):
    """
    User roles
    """

    TENANT_SUPER_USER = "tenant_super_user", _("Tenant Super User")
    PROJECT_CREATOR = "project_creator", _("Project Creator")
    PROJECT_ADMIN = "project_admin", _("Project Administrator")
    PROJECT_MANAGER = "project_manager", _("Project Manager")
    INSTRUCTOR = "instructor", _("Instructor")
    CONTROLLER = "controller", _("Controller")
    GUEST = "guest", _("Guest")


class UserRole(models.Model):
    id = UUIDPrimaryKeyField()
    user = models.ForeignKey("user.User", on_delete=models.CASCADE, related_name="project_roles")
    project = models.ForeignKey(
        "project.Project", on_delete=models.CASCADE, related_name="user_roles", null=True, blank=True
    )
    role = models.CharField(max_length=30, choices=Role.choices)
    library = models.ForeignKey(
        "project.Library", on_delete=models.CASCADE, null=True, blank=True, related_name="user_roles"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        "user.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_roles"
    )

    class Meta:
        verbose_name = _("Project User Role")
        verbose_name_plural = _("Project User Roles")
        constraints = [
            models.UniqueConstraint(fields=["user", "role", "project"], name="unique_user_role_project"),
            models.CheckConstraint(
                check=models.Q(role__in=[choice[0] for choice in Role.choices]),
                name="%(app_label)s_%(class)s_role_valid",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.get_role_display()} ({self.project})"
