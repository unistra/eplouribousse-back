from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured, ValidationError

from epl.apps.user.models import User
from epl.apps.user.validators import ZxcvbnPasswordValidator
from epl.tests import TestCase


class ZxcvbnValidatorTest(TestCase):
    def test_min_score_must_be_an_integer(self):
        with self.assertRaises(ImproperlyConfigured):
            ZxcvbnPasswordValidator(min_score="not_an_integer")

    def test_validate_with_user_instance_fills_inputs(self):
        validator = ZxcvbnPasswordValidator()
        user = User.objects.create_user(
            "test_user", email="first.last@example.com", first_name="First", last_name="Last"
        )
        with patch("epl.apps.user.validators.zxcvbn") as mock_zxcvbn:
            mock_zxcvbn.return_value = {"score": 4}
            validator(password="test_password", user=user)  # noqa: S106
            mock_zxcvbn.assert_called_once_with(
                "test_password",
                user_inputs=["First", "Last", "first.last@example.com", "test_user"],
            )

    def test_validate_with_weak_password(self):
        validator = ZxcvbnPasswordValidator()
        with patch("epl.apps.user.validators.zxcvbn") as mock_zxcvbn:
            mock_zxcvbn.return_value = {"score": 1, "feedback": {"warning": "Weak password warning"}}
            with self.assertRaises(ValidationError) as cm:
                validator("weak password")

            self.assertIn("The password is too weak", str(cm.exception))
            self.assertIn("Weak password warning", str(cm.exception))
