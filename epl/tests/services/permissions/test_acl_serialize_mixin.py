from unittest.mock import patch

from django.db import models
from rest_framework.permissions import BasePermission
from rest_framework.serializers import Serializer
from rest_framework.test import APIRequestFactory
from rest_framework.test import APITestCase as TestCase
from rest_framework.viewsets import GenericViewSet

from epl.apps.user.models import User
from epl.services.permissions.serializers import AclField, AclSerializerMixin


class TestPermissionClass(BasePermission):
    @staticmethod
    def user_has_permission(permission, user, instance):
        return True


class TestModel(models.Model):
    _extended_permissions = [
        "custom_action",
    ]

    def __str__(self):
        return ""


class TestModelWithoutExtendedPermissions(models.Model):
    def __str__(self):
        return ""


class TestSerializer(AclSerializerMixin, Serializer):
    acl = AclField()

    class Meta:
        model = TestModel
        fields = ["acl"]


class TestViewSet(GenericViewSet):
    model = TestModel
    serializer_class = TestSerializer
    permission_classes = [TestPermissionClass]

    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)


class AclSerializerMixinTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="user@eplouribousse.fr")
        factory = APIRequestFactory()
        self.request = factory.post("/")
        self.request.user = user
        view = TestViewSet()
        self.serializer = TestSerializer(
            data={},
            context={
                "request": self.request,
                "view": view,
            },
        )

    def test_get_permissions_merges_base_and_extended_permissions(self):
        model = TestModel()
        all_permissions = self.serializer._get_permissions(model)
        self.assertListEqual(
            sorted(all_permissions),
            sorted(["retrieve", "update", "partial_update", "destroy", "custom_action"]),
        )

    def test_get_permissions_returns_only_base_permissions_if_no_extended_permissions(self):
        model = TestModelWithoutExtendedPermissions()
        all_permissions = self.serializer._get_permissions(model)
        self.assertListEqual(
            sorted(all_permissions),
            sorted(["retrieve", "update", "partial_update", "destroy"]),
        )

    def test_get_permission_classes(self):
        permission_classes = self.serializer._get_permission_classes()
        self.assertListEqual(
            sorted(permission_classes),
            sorted([TestPermissionClass]),
        )

    def test_get_permission_classes_needs_view_in_the_context(self):
        self.serializer.context["view"] = None
        with self.assertRaises(ValueError):
            self.serializer._get_permission_classes()

    def test_get_permission_classes_needs_view_to_be_generic_api_view(self):
        self.serializer.context["view"] = object()
        with self.assertRaises(ValueError):
            self.serializer._get_permission_classes()

    def test_get_acl(self):
        with patch.object(
            TestPermissionClass, "user_has_permission", autospec=True, return_value=False
        ) as user_has_permission:
            acls = self.serializer.get_acl(TestModel())
        self.assertListEqual(
            sorted(acls.keys()),
            sorted(["retrieve", "update", "partial_update", "destroy", "custom_action"]),
        )
        self.assertListEqual(
            list(acls.values()),
            [False, False, False, False, False],
        )
        self.assertEqual(
            user_has_permission.call_count,
            5,
        )
