from django.conf import settings
from django.core.mail import send_mail
from django.db.models import TextChoices
from django.utils import html
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


class SubjectChoices(TextChoices):
    INFO = "ask_info", _("Ask for information")
    BUG = "bug", _("Report a bug")
    COMPLAINT = "complaint", _("Make a complaint")
    SUGGESTION = "suggestion", _("Make a suggestion")
    REVIEW = "review", _("Give a review")
    OTHER = "other", _("Other")


class ContactSupportSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=False, help_text=_("Email address of the sender. Required if not authenticated.")
    )
    subject = serializers.ChoiceField(choices=SubjectChoices, allow_blank=False)
    message = serializers.CharField(required=True, max_length=1000)

    def validate_email(self, value):
        if not self.context["request"].user.is_authenticated and not value:
            raise serializers.ValidationError(_("Email is required for unauthenticated users."))
        return value

    def validate_message(self, message):
        message = message.strip()
        message = html.escape(strip_tags(message))
        return message

    def save(self, **kwargs):
        if user := self.context["request"].user if self.context["request"].user.is_authenticated else None:
            email = user.email
        else:
            email = self.validated_data["email"]
        subject = _("Contact form: {subject_label}").format(
            subject_label=str(SubjectChoices(self.validated_data["subject"]).label)
        )
        message = self.validated_data["message"]

        send_mail(
            subject=subject,
            message=message,
            from_email=email,
            recipient_list=[settings.CONTACT_EMAIL],
        )
