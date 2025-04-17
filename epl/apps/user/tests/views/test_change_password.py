from django_tenants.urlresolvers import reverse

from epl.tests import TestCase


class TestChangePassword(TestCase):
    def test_anonymous_access_is_forbidden(self):
        response = self.client.patch(reverse("change_password"))
        self.assertEqual(response.status_code, 401)
