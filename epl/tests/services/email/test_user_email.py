from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core import mail, signing
from django.utils.translation import gettext as _
from rest_framework.request import Request

from epl.apps.user.models import User
from epl.services.user.email import send_invite_email, send_password_change_email, send_password_reset_email
from epl.tests import TestCase


class TestUserEmailServices(TestCase):
    def create_user(self, username="test@test.com", password="&siE9S3rVVEn1UvTM4b@"):  # noqa: S107
        user = User.objects.create_user(username, email=username, password=password)
        return user

    def test_send_password_change_email(self):
        user = self.create_user()
        send_password_change_email(user)

        # Check that an email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Verify email subject
        expected_subject = f"[eplouribousse] {_('Password Change')}"
        self.assertEqual(mail.outbox[0].subject, expected_subject)

        # Verify email recipient
        self.assertEqual(mail.outbox[0].to, [user.email])

        # Verify sender email
        self.assertEqual(mail.outbox[0].from_email, settings.DEFAULT_FROM_EMAIL)

        # Verify email content contains important elements
        email_content = mail.outbox[0].body
        self.assertIn(
            _("We inform you that the password for your Eplouribousse account has been recently changed"), email_content
        )
        self.assertIn(_("If you initiated this change"), email_content)
        self.assertIn(_("If you did NOT make this change"), email_content)
        self.assertIn(settings.EMAIL_SUPPORT, email_content)

    def test_send_password_reset_email(self):
        user = self.create_user()
        front_domain = "http://sxb.epl.localhost:5173"
        send_password_reset_email(user=user, front_domain=front_domain)

        # Check that an email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Verify email subject
        expected_subject = f"[eplouribousse] {_('Password Reset')}"
        self.assertEqual(mail.outbox[0].subject, expected_subject)

        # Verify email recipient
        self.assertEqual(mail.outbox[0].to, [user.email])

        # Verify sender email
        self.assertEqual(mail.outbox[0].from_email, settings.DEFAULT_FROM_EMAIL)

        # Verify email content contains important elements
        email_content = mail.outbox[0].body
        self.assertIn(_("Did you forget your password ?"), email_content)
        self.assertIn(_("Click on the link to reset your password"), email_content)
        self.assertIn(_("This link is only valid for 1 hour"), email_content)

    @patch("epl.services.user.email.send_mail")
    @patch("epl.services.user.email.render_to_string")
    @patch("epl.services.user.email.get_front_domain")
    def test_send_invite_email(self, mock_get_front_domain, mock_render_to_string, mock_send_mail):
        mock_get_front_domain.return_value = "http://testdomain"
        mock_render_to_string.return_value = "Email content"
        signer = signing.TimestampSigner()
        request = MagicMock(spec=Request)
        email = "invitee@example.com"
        project_id = "123"
        library_id = "456"
        role = "INSTRUCTOR"
        assigned_by_id = "789"

        send_invite_email(
            email=email,
            request=request,
            signer=signer,
            project_id=project_id,
            library_id=library_id,
            role=role,
            assigned_by_id=assigned_by_id,
        )

        args, kwargs = mock_render_to_string.call_args
        context = args[1]
        invitation_link = context["invitation_link"]

        self.assertTrue(invitation_link.startswith("http://testdomain/create-account?t="))
        token = invitation_link.split("t=")[1]
        data = signer.unsign_object(token)
        self.assertEqual(data["email"], email)
        self.assertEqual(data["project_id"], project_id)
        self.assertEqual(data["library_id"], library_id)
        self.assertEqual(data["role"], role)
        self.assertEqual(data["assigned_by_id"], assigned_by_id)
