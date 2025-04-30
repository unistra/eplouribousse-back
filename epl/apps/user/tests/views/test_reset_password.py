from django.core.signing import TimestampSigner
from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context

from epl.apps.user.models import User
from epl.tests import TestCase


class TestResetPassword(TestCase):
    def create_user(self, username="test@test.com", password="&siE9S3rVVEn1UvTM4b@"):  # noqa: S107
        with tenant_context(self.tenant):
            user = User.objects.create_user(username, email=username, password=password)
        return user

    def test_successful_password_reset_email(self):
        old_password = "_Here is my 1st password"  # noqa: S105

        user = self.create_user(password=old_password)
        response = self.post(
            reverse("send_reset_email"),
            {"email": user.username},
            content_type="application/json",
            user=user,
        )

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()

    def test_successful_password_reset(self):
        new_password = "_Here is my 2nd and new password"  # noqa: S105
        signer = TimestampSigner(salt="reset-password")
        user = self.create_user()
        token = signer.sign(user.username)

        response = self.patch(
            reverse("reset_password"),
            {
                "token": token,
                "new_password": new_password,
                "confirm_password": new_password,
            },
            content_type="application/json",
            user=user,
        )

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password(new_password))

    def test_wrong_token_password_reset_return_400(self):
        new_password = "_Here is my 2nd and new password"  # noqa: S105
        user = self.create_user()

        response = self.patch(
            reverse("reset_password"),
            {
                "token": "wrong_token",
                "new_password": new_password,
                "confirm_password": new_password,
            },
            content_type="application/json",
            user=user,
        )

        self.assertEqual(response.status_code, 400)
