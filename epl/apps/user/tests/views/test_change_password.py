from django_tenants.urlresolvers import reverse

from epl.apps.user.models import User
from epl.tests import TestCase


class TestChangePassword(TestCase):
    def test_anonymous_access_is_forbidden(self):
        response = self.client.patch(reverse("change_password"))
        self.assertEqual(response.status_code, 401)

    def create_and_login_user(self, username="test@test.com", password="&siE9S3rVVEn1UvTM4b@"):  # noqa: S107
        user = User.objects.create_user(username, email=username, password=password)
        self.client.login(username=username, password=password)
        return user

    def test_successful_password_change(self):
        old_password = "_Here is my 1st password"  # noqa: S105
        new_password = "_Here is my 2nd and new password"  # noqa: S105

        user = self.create_and_login_user(password=old_password)

        response = self.client.patch(
            reverse("change_password"),
            {
                "old_password": old_password,
                "new_password": new_password,
                "confirm_password": new_password,
            },
        )

        self.assertEqual(response.status_code, 200)

        user.refresh_from_db()
        self.assertTrue(user.check_password(new_password))

    # Test incorrect old password

    # Test password mismatch

    # Test weak password validation

    # Test missing fields
