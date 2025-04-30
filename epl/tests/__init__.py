from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient as OriginalTenantClient
from rest_framework import status
from rest_framework.status import HTTP_200_OK
from rest_framework_simplejwt.tokens import AccessToken


class TenantClient(OriginalTenantClient):
    _token = None

    def force_authenticate(self, user):
        if user.is_authenticated:
            token = AccessToken.for_user(user)
            self._token = token

    # def get(
    #     self,
    #     path,
    #     data=None,
    #     follow=False,
    #     secure=False,
    #     *,
    #     headers=None,
    #     **extra,
    # ):
    #     if user := extra.pop("user", None):
    #         self.force_authenticate(user)
    #     if self._token:
    #         super().get(
    #             path,
    #             data=data,
    #             follow=follow,
    #             secure=secure,
    #             headers=headers,
    #             HTTP_AUTHORIZATION=f"Bearer {self._token}",
    #             **extra,
    #         )
    #     return super().get(path, data=data, follow=follow, secure=secure, headers=headers, **extra)
    #
    # def patch(
    #     self,
    #     path,
    #     data="",
    #     content_type="application/octet-stream",
    #     follow=False,
    #     secure=False,
    #     *,
    #     headers=None,
    #     **extra,
    # ):
    #     if user := extra.pop("user", None):
    #         self.force_authenticate(user)
    #     if self._token:
    #         return super().patch(
    #             path,
    #             data=data,
    #             content_type=content_type,
    #             follow=follow,
    #             secure=secure,
    #             headers=headers,
    #             HTTP_AUTHORIZATION=f"Bearer {self._token}",
    #             **extra,
    #         )
    #     return super().patch(
    #         path,
    #         data=data,
    #         content_type=content_type,
    #         follow=follow,
    #         secure=secure,
    #         headers=headers,
    #         **extra,
    #     )


class TestCase(TenantTestCase):
    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)

    def _perform_request(self, method, path, *args, **kwargs):
        if user := kwargs.pop("user", None):
            self.client.force_authenticate(user)
        if self.client._token:
            kwargs["HTTP_AUTHORIZATION"] = f"Bearer {self.client._token}"
        return getattr(self.client, method)(path, *args, **kwargs)

    def get(self, path, *args, **kwargs):
        return self._perform_request("get", path, *args, **kwargs)

    def post(self, path, *args, **kwargs):
        return self._perform_request("post", path, *args, **kwargs)

    def put(self, path, *args, **kwargs):
        return self._perform_request("put", path, *args, **kwargs)

    def patch(self, path, *args, **kwargs):
        return self._perform_request("patch", path, *args, **kwargs)

    def delete(self, path, *args, **kwargs):
        return self._perform_request("delete", path, *args, **kwargs)

    def response_ok(self, response):
        self.assertEqual(response.status_code, HTTP_200_OK)

    def response_created(self, response):
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def response_no_content(self, response):
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def response_bad_request(self, response):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def response_unauthorized(self, response):
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def response_forbidden(self, response):
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def response_not_found(self, response):
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
