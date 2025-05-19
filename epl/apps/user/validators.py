from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils.translation import gettext_lazy as _
from zxcvbn import zxcvbn


class ZxcvbnPasswordValidator:
    code = "password_too_weak"

    def __init__(self, min_score: int = 3) -> None:
        try:
            self.min_score = int(min_score)
        except ValueError:
            raise ImproperlyConfigured(_("The min_score parameter of the ZxcvbnPasswordValidator must be an integer."))

    def __call__(self, *args, **kwargs) -> None:
        self.validate(*args, **kwargs)

    def validate(self, password: str, user=None) -> None:
        user_inputs = []

        if user is not None:
            for attribute in ["first_name", "last_name", "email", "username"]:
                user_inputs.append(getattr(user, attribute))

        results = zxcvbn(password, user_inputs=user_inputs)
        if results.get("score", 0) < self.min_score:
            msg = _("The password is too weak")
            raise ValidationError(
                {msg, results.get("feedback", {}).get("warning", [])},
                code=self.code,
            )

    def get_help_text(self):
        return _("The password is too weak")
