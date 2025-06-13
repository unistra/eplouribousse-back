from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from epl.models import UUIDPrimaryKeyField


class Status(models.IntegerChoices):
    CREATED = 10, _("Created")
    DRAFT = 20, _("Draft")
    REVIEW = 30, _("Review")
    ACTIVE = 40, _("Active")


class Project(models.Model):
    id = UUIDPrimaryKeyField()
    name = models.CharField(_("Name"), max_length=255)
    description = models.TextField(_("Description"), blank=True)
    is_private = models.BooleanField(_("Is private"), default=False)
    active_after = models.DateTimeField(_("Active after"), default=now)
    status = models.IntegerField(_("Status"), choices=Status.choices, default=Status.CREATED)
    settings = models.JSONField(_("Settings"), default=dict)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

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
