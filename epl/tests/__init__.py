from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient


class TestCase(TenantTestCase):
    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
