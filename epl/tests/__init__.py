from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient as OriginalTenantClient
from rest_framework_simplejwt.tokens import AccessToken


class TenantClient(OriginalTenantClient):
    _token = None

    def force_authenticate(self, user):
        if user.is_authenticated:
            token = AccessToken.for_user(user)
            self._token = token

    def get(
        self,
        path,
        data=None,
        follow=False,
        secure=False,
        *,
        headers=None,
        **extra,
    ):
        if user := extra.pop("user"):
            self.force_authenticate(user)
        if self._token:
            super().get(
                path,
                data=data,
                follow=follow,
                secure=secure,
                headers=headers,
                HTTP_AUTHORIZATION=f"Bearer {self._token}",
                **extra,
            )
        super().get(path, data=data, follow=follow, secure=secure, headers=headers, **extra)

    def patch(
        self,
        path,
        data="",
        content_type="application/octet-stream",
        follow=False,
        secure=False,
        *,
        headers=None,
        **extra,
    ):
        if user := extra.pop("user"):
            self.force_authenticate(user)
        if self._token:
            return super().patch(
                path,
                data=data,
                content_type=content_type,
                follow=follow,
                secure=secure,
                headers=headers,
                HTTP_AUTHORIZATION=f"Bearer {self._token}",
                **extra,
            )
        return super().patch(
            path,
            data=data,
            content_type=content_type,
            follow=follow,
            secure=secure,
            headers=headers,
            **extra,
        )


class TestCase(TenantTestCase):
    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
