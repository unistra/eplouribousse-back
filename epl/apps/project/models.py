from django.db import models
from django.db.models import Prefetch
from django.utils.translation import gettext_lazy as _

from epl.apps.user.models import User
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

    @classmethod
    def get_users_with_roles_for_project(cls, project):
        """
        Returns a list of users with their roles for a given project.
        """
        # get all roles for the project, used in Prefetch and avoid N+1 queries
        # Thanks to Prefetch(queryset=project_user_roles), django loads only the roles for the current project
        project_user_roles = cls.objects.filter(project=project)  # get all roles for the project, used in Prefetch

        users_with_project_roles = (
            User.objects.filter(project_roles__project=project)  # Filters the users who have roles in the given project
            .distinct()
            .prefetch_related(
                Prefetch(
                    "project_roles",
                    queryset=project_user_roles,
                    to_attr="roles_for_this_project",
                )
            )
        )

        result_users = []
        for user in users_with_project_roles:
            user.roles = [user_role.role for user_role in user.roles_for_this_project]
            result_users.append(user)

        return result_users
