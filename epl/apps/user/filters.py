from django.utils.translation import gettext_lazy as _
from rest_framework import filters
from rest_framework.exceptions import ValidationError

from epl.apps.project.models import Role, UserRole


class UserRoleFilter(filters.BaseFilterBackend):
    """
    Filter users by their role (superuser or project_creator).
    """

    role_param = "role"
    role_param_description = _("Filter users by role (superuser or project_creator)")

    def filter_queryset(self, request, queryset, view):
        role = request.query_params.get(self.role_param, None)

        if not role:
            return queryset

        role_lower = role.lower()

        if role_lower == Role.TENANT_SUPER_USER:
            return queryset.filter(is_superuser=True)
        elif role_lower == Role.PROJECT_CREATOR:
            # Filter users who have the PROJECT_CREATOR role in UserRole table
            user_ids = UserRole.objects.filter(
                role=Role.PROJECT_CREATOR,
            ).values_list("user_id", flat=True)
            return queryset.filter(id__in=user_ids)
        else:
            raise ValidationError({self.role_param: _("Invalid role. Must be 'superuser' or 'project_creator'.")})

    def get_schema_operation_parameters(self, view):
        return [
            {
                "name": self.role_param,
                "required": False,
                "in": "query",
                "description": str(self.role_param_description),
                "schema": {
                    "type": "string",
                    "enum": ["superuser", "project_creator"],
                },
            },
        ]
