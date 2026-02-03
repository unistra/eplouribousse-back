from django.conf import settings
from django.core import mail
from django_tenants.urlresolvers import reverse

from epl.apps.project.serializers.contact import SubjectChoices
from epl.apps.project.tests.factories.user import UserFactory
from epl.tests import TestCase


class ContactSupportViewTests(TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.url = reverse("contact-support")

    def test_contact_support_is_not_authenticated(self):
        data = {
            "email": "user@eplouribousse.fr",
            "subject": SubjectChoices.INFO,
            "message": "This is the message",
        }
        response = self.post(self.url, data)
        self.response_created(response)
        self.assertEqual(
            len(mail.outbox),
            1,
        )
        self.assertEqual(
            mail.outbox[0].body,
            "This is the message",
        )
        self.assertEqual(
            mail.outbox[0].subject,
            f"Eplouribousse - Contact form: {SubjectChoices.INFO.label}",
        )
        self.assertEqual(mail.outbox[0].from_email, settings.CONTACT_EMAIL)
        self.assertEqual(mail.outbox[0].reply_to, ["user@eplouribousse.fr"])

    def test_contact_support_with_authenticated_user_does_not_require_email(self):
        data = {
            "subject": SubjectChoices.BUG,
            "message": "This is another message",
        }
        response = self.post(self.url, data, user=self.user)
        self.response_created(response)
        self.assertEqual(
            len(mail.outbox),
            1,
        )
        self.assertEqual(
            mail.outbox[0].body,
            "This is another message",
        )
        self.assertEqual(
            mail.outbox[0].subject,
            f"Eplouribousse - Contact form: {SubjectChoices.BUG.label}",
        )
        self.assertEqual(mail.outbox[0].from_email, settings.CONTACT_EMAIL)
        self.assertEqual(mail.outbox[0].reply_to, [self.user.email])

    def test_recipient_is_contact_email(self):
        data = {
            "email": "user@eplouribousse.fr",
            "subject": SubjectChoices.COMPLAINT,
            "message": "This is the message",
        }
        response = self.post(self.url, data)
        self.response_created(response)
        self.assertEqual(
            len(mail.outbox),
            1,
        )
        self.assertEqual(
            mail.outbox[0].to,
            [settings.CONTACT_EMAIL],
        )

    def test_subject_is_required(self):
        data = {
            "message": "This is the message",
        }
        response = self.post(self.url, data, user=self.user)
        self.response_bad_request(response)
        self.assertIn("subject", response.json())

    def test_message_is_required(self):
        data = {
            "subject": SubjectChoices.OTHER,
        }
        response = self.post(self.url, data, user=self.user)
        self.response_bad_request(response)
        self.assertIn("message", response.json())

    def test_email_must_be_valid(self):
        data = {
            "email": "invalid-email",
            "subject": SubjectChoices.INFO,
            "message": "This is the message",
        }
        response = self.post(self.url, data)
        self.response_bad_request(response)
        self.assertIn("email", response.json())

    def test_message_is_cleaned(self):
        data = {"subject": SubjectChoices.SUGGESTION, "message": "<script>alert('xss');</script>   This is a message"}
        response = self.post(self.url, data, user=self.user)
        self.response_created(response)
        self.assertEqual(
            len(mail.outbox),
            1,
        )
        self.assertEqual(mail.outbox[0].body, "alert(&#x27;xss&#x27;);   This is a message")
