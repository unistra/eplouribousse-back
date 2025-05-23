from django.db import models
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import BasePermission


class AclSerializerMixin(serializers.Serializer):
    base_permissions = [
        "retrieve",
        "update",
        "partial_update",
        "destroy",
    ]
    extended_permissions = []

    def get_acl(self, instance):
        permissions = self._get_permissions(instance)
        permission_classes = self._get_permission_classes()
        user = self.context["request"].user
        return {
            permission: self._check_permission(
                permission_classes,
                permission,
                user,
                instance,
            )
            for permission in permissions
        }

    @staticmethod
    def _check_permission(permission_classes, permission, user, instance) -> bool:
        """
        Check the permission on each permission class
        """
        return any(
            permission_class.user_has_permission(permission, user, instance)
            for permission_class in permission_classes
            if hasattr(permission_class, "user_has_permission") and callable(permission_class.user_has_permission)
        )

    def _get_permissions(self, instance: models.Model) -> list[str]:
        """
        Get all permissions: base_permissions and extended_permissions that
        can be defined on the model's Meta class
        """
        extended_permissions = getattr(
            instance.__class__,
            "_extended_permissions",
            [],
        )
        return list(set(self.base_permissions + extended_permissions))

    def _get_permission_classes(self) -> list[BasePermission]:
        """
        Get the permission classes defined on the view
        """

        view = self.context.get("view", None)
        if view is None or not isinstance(view, GenericAPIView):
            raise ValueError(_("View is not in serializer context or is not a GenericApiView"))

        return getattr(view, "permission_classes", [])


class AclField(serializers.SerializerMethodField): ...
