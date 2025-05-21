import uuid

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django_tenants.urlresolvers import reverse
from django_tenants.utils import tenant_context

from epl.apps.user.models import User
from epl.tests import TestCase


class TestResetPasswordView(TestCase):
    def create_user(self, username="test@eplouribousse.fr", password="&siE9S3rVVEn1UvTM4b@"):  # noqa: S107
        with tenant_context(self.tenant):
            user = User.objects.create_user(username, email=username, password=password)
        return user

    def test_send_password_reset_email(self):
        user = self.create_user()
        response = self.post(
            reverse("send_reset_email"),
            {"email": user.email},
            content_type="application/json",
        )

        self.response_ok(response)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [user.email])

    def test_send_password_fails_silently_if_user_does_not_exist(self):
        response = self.post(
            reverse("send_reset_email"),
            {"email": "9hDpC@example.com"},
            content_type="application/json",
        )
        self.response_ok(response)
        self.assertEqual(len(mail.outbox), 0)

    def test_successfull_password_reset(self):
        user = self.create_user()
        new_password = "finite-scratch-driller-majestic-crudeness-tattle"  # noqa: S105

        response = self.patch(
            reverse("reset_password"),
            {
                "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": PasswordResetTokenGenerator().make_token(user),
                "new_password": new_password,
                "confirm_password": new_password,
            },
            content_type="application/json",
        )
        user.refresh_from_db()
        self.response_ok(response)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [user.email])
        self.assertTrue(user.check_password(new_password))

    def test_reset_password_fails_if_uidb64_is_invalid(self):
        user = self.create_user()
        new_password = "finite-scratch-driller-majestic-crudeness-tattle"  # noqa: S105

        response = self.patch(
            reverse("reset_password"),
            {
                "uidb64": urlsafe_base64_encode(force_bytes(uuid.uuid4())),
                "token": PasswordResetTokenGenerator().make_token(user),
                "new_password": new_password,
                "confirm_password": new_password,
            },
            content_type="application/json",
        )
        user.refresh_from_db()
        self.response_bad_request(response)
        self.assertIn("Invalid uidb64", str(response.content))
        self.assertFalse(user.check_password(new_password))

    def test_reset_password_fails_if_token_is_invalid(self):
        user = self.create_user()
        new_password = "finite-scratch-driller-majestic-crudeness-tattle"  # noqa: S105

        response = self.patch(
            reverse("reset_password"),
            {
                "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": "invalid_token",
                "new_password": new_password,
                "confirm_password": new_password,
            },
            content_type="application/json",
        )
        user.refresh_from_db()
        self.response_bad_request(response)
        self.assertIn("Token is invalid", str(response.content))
        self.assertFalse(user.check_password(new_password))

    def test_reset_password_fails_if_passwords_do_not_match(self):
        user = self.create_user()
        new_password = "finite-scratch-driller-majestic-crudeness-tattle"  # noqa: S105

        response = self.patch(
            reverse("reset_password"),
            {
                "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": PasswordResetTokenGenerator().make_token(user),
                "new_password": new_password,
                "confirm_password": "wrong_password",
            },
            content_type="application/json",
        )
        user.refresh_from_db()
        self.response_bad_request(response)
        self.assertIn("New password and confirm password do not match", str(response.content))
        self.assertFalse(user.check_password(new_password))
