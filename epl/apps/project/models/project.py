from django.db import models
from django.utils.translation import gettext_lazy as _

from epl.models import UUIDPrimaryKeyField


class Project(models.Model):
    id = UUIDPrimaryKeyField()
    name = models.CharField(_("Name"), max_length=255)
    description = models.TextField(_("Description"), blank=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Project")
        verbose_name_plural = _("Projects")

    def __str__(self):
        return self.name


class UserRole(models.Model):
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

    id = UUIDPrimaryKeyField()
    user = models.ForeignKey("user.User", on_delete=models.CASCADE, related_name="project_roles")
    project = models.ForeignKey("project.Project", on_delete=models.CASCADE, related_name="user_roles")
    role = models.CharField(max_length=30, choices=Role.choices)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        "user.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_roles"
    )

    class Meta:
        verbose_name = _("Project User Role")
        verbose_name_plural = _("Project User Roles")
        constraints = [
            models.UniqueConstraint(fields=["user", "role", "project"], name="unique_user_role_project"),
        ]

    def __str__(self):
        return f"{self.user} - {self.get_role_display()} ({self.project})"
