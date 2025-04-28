from django.urls import reverse
from rest_framework import status

from epl.tests import TestCase


class ConsortiumViewTests(TestCase):
    def test_get_consortium_info_success(self):
        """
        Tests the successful retrieval of consortium information.
        """
        url = reverse("consortium")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], self.tenant.name)
        self.assertEqual(response.data["settings"], self.tenant.tenant_settings)
        self.assertIn("id", response.data)
