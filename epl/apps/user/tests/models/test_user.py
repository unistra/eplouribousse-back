from epl.apps.user.models import User
from epl.tests import TestCase


class TestUser(TestCase):
    def test_user_str_with_first_and_last_name(self):
        user = User.objects.create_user(
            "test_user", first_name="First", last_name="Last", email="first.last@example.com"
        )
        self.assertEqual(
            str(user),
            "First Last",
        )

    def test_user_with_first_name_only(self):
        user = User.objects.create_user("test_user", first_name="First", email="first.last@example.com")
        self.assertEqual(
            str(user),
            "First",
        )

    def test_user_with_last_name_only(self):
        user = User.objects.create_user("test_user", last_name="Last", email="first.last@example.com")
        self.assertEqual(
            str(user),
            "Last",
        )

    def test_user_str_with_no_first_or_last_name(self):
        user = User.objects.create_user("test_user", email="first.last@example.com")
        self.assertEqual(
            str(user),
            "test_user",
        )
