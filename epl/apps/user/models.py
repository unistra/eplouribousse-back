from typing import TypeVar

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

from epl.models import UUIDPrimaryKeyField

T = TypeVar("T")


class UserQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class CustomUserManager(UserManager.from_queryset(UserQuerySet)):
    use_in_migrations = True

    @staticmethod
    def _check_username_and_email(username: T, email: T) -> tuple[T, T]:
        if not email:
            raise ValueError(_("The Email must be set"))
        if not username:
            username = email
        return username, email

    def create_user(self, username=None, email=None, password=None, **extra_fields) -> "User":
        username, email = self._check_username_and_email(username, email)
        return super().create_user(username, email, password, **extra_fields)

    def create_superuser(self, username=None, email=None, password=None, **extra_fields) -> "User":
        username, email = self._check_username_and_email(username, email)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    id = UUIDPrimaryKeyField()
    email = models.EmailField(_("Email address"), unique=True)
    settings = models.JSONField(default=dict)

    objects = CustomUserManager()

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = [
            "last_name",
            "first_name",
        ]

    def __str__(self) -> str:
        name: str = f"{self.first_name} {self.last_name}".strip()
        return name or self.username


class UserRole(models.Model):
    # Role constants
    TENANT_SUPER_USER = "tenant_super_user"
    PROJECT_CREATOR = "project_creator"
    PROJECT_MANAGER = "project_manager"
    INSTRUCTOR = "instructor"
    CONTROLLER = "controller"
    GUEST = "guest"

    ROLE_CHOICES = [
        (TENANT_SUPER_USER, _("Tenant Super User")),
        (PROJECT_CREATOR, _("Project Creator")),
        (PROJECT_MANAGER, _("Project Manager")),
        (INSTRUCTOR, _("Instructor")),
        (CONTROLLER, _("Controller")),
        (GUEST, _("Guest")),
    ]

    id = UUIDPrimaryKeyField()
    user = models.ForeignKey("user.User", on_delete=models.CASCADE, related_name="project_roles")
    project = models.ForeignKey("project.Project", on_delete=models.CASCADE, related_name="user_roles")
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        "user.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_roles"
    )

    class Meta:
        unique_together = ("user", "project", "role")
        verbose_name = _("Project User Role")
        verbose_name_plural = _("Project User Roles")

    def __str__(self):
        return f"{self.user} - {self.get_role_display()} ({self.project})"
