from django.urls import reverse

from epl.tests import TestCase


class ConsortiumViewTests(TestCase):
    def test_get_consortium_info_success(self):
        """
        Tests the successful retrieval of consortium information.
        """
        url = reverse("consortium")
        response = self.client.get(url)

        self.response_ok(response)
        self.assertEqual(response.data["name"], self.tenant.name)
        self.assertEqual(response.data["settings"], self.tenant.tenant_settings)
        self.assertIn("id", response.data)
