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
        acl_field = self.fields["acl"]
        custom_permission_classes = getattr(acl_field, "permission_classes", None)
        exclude = getattr(acl_field, "exclude", [])
        include = getattr(acl_field, "include", [])
        permissions = self._get_permissions(instance, include=include, exclude=exclude)
        permission_classes = self._get_permission_classes(permission_classes=custom_permission_classes)
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

    def _get_permissions(
        self, instance: models.Model, include: list[str] = None, exclude: list[str] = None
    ) -> list[str]:
        """
        Get all permissions: base_permissions and extended_permissions that
        can be defined on the model's Meta class
        """
        extended_permissions = getattr(
            instance.__class__,
            "_extended_permissions",
            [],
        )
        # All permissions defined on the model
        permissions = list(set(self.base_permissions + extended_permissions))

        if include:
            # If include is defined, return only those permissions
            # Include takes precedence over exclude
            return [perm for perm in permissions if perm in include]
        if exclude:
            # If exclude is defined, return all permissions except those
            return [perm for perm in permissions if perm not in exclude]
        return permissions

    def _get_permission_classes(self, permission_classes: list[BasePermission] = None) -> list[BasePermission]:
        """
        Get the permission classes defined on the view
        """

        if permission_classes:
            return permission_classes

        view = self.context.get("view", None)
        if view is None or not isinstance(view, GenericAPIView):
            raise ValueError(_("View is not in serializer context or is not a GenericApiView"))

        return getattr(view, "permission_classes", [])


class AclField(serializers.SerializerMethodField):
    def __init__(self, **kwargs):
        if permission_classes := kwargs.pop("permission_classes", None):
            self.permission_classes = permission_classes
        if exclude := kwargs.pop("exclude", None):
            self.exclude = exclude
        if include := kwargs.pop("include", None):
            self.include = include
        super().__init__(**kwargs)
