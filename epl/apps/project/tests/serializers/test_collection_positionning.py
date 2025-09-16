from django.core import mail
from django_tenants.utils import tenant_context

from epl.apps.project.models import Collection, Role
from epl.apps.project.models.collection import Arbitration
from epl.apps.project.serializers.collection import PositionSerializer
from epl.apps.project.tests.factories.collection import CollectionFactory
from epl.apps.project.tests.factories.library import LibraryFactory
from epl.apps.project.tests.factories.project import ProjectFactory
from epl.apps.project.tests.factories.resource import ResourceFactory
from epl.apps.project.tests.factories.user import UserWithRoleFactory
from epl.tests import TestCase


class PositioningNotificationTest(TestCase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.tenant):
            self.project = ProjectFactory()

            self.library1 = LibraryFactory(project=self.project)
            self.instructor1 = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library1)

            self.library2 = LibraryFactory(project=self.project)
            self.instructor2 = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library2)

            self.library3 = LibraryFactory(project=self.project)
            self.instructor3 = UserWithRoleFactory(role=Role.INSTRUCTOR, project=self.project, library=self.library3)

            self.resource = ResourceFactory(project=self.project)

            self.collection1 = CollectionFactory(resource=self.resource, library=self.library1, project=self.project)
            self.collection2 = CollectionFactory(resource=self.resource, library=self.library2, project=self.project)
            self.collection3 = CollectionFactory(resource=self.resource, library=self.library3, project=self.project)

    def _position_collection(self, collection: Collection, position: int, user):
        serializer = PositionSerializer(
            instance=collection,
            data={"position": position},
            context={"request": self.mock_request(user=user)},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        self.resource.refresh_from_db()

    def test_sends_email_on_type1_arbitration(self):
        """
        Vérifie que l'email est envoyé aux instructeurs concernés lors d'un arbitrage de type 1.
        """
        # GIVEN: La collection 1 est déjà en position 1
        self._position_collection(self.collection1, 1, self.instructor1)
        mail.outbox = []

        # WHEN: La collection 2 est aussi positionnée en 1, créant un arbitrage
        self._position_collection(self.collection2, 1, self.instructor2)

        # THEN:
        self.assertEqual(self.resource.arbitration, Arbitration.ONE)
        # On s'attend à 2 emails, car la vérification des settings est retirée
        self.assertEqual(len(mail.outbox), 2)

        recipients = {email.to[0] for email in mail.outbox}
        # Les destinataires sont les instructeurs des collections de rang 1
        self.assertSetEqual(recipients, {self.instructor1.email, self.instructor2.email})

        for email in mail.outbox:
            if email.to[0] == self.instructor1.email:
                self.assertIn(self.library1.code, email.subject)
            if email.to[0] == self.instructor2.email:
                self.assertIn(self.library2.code, email.subject)

            self.assertIn(self.resource.code, email.subject)
            self.assertIn("arbitrage 1", email.subject)

    def test_no_email_if_first_at_rank_1(self):
        """
        Vérifie qu'aucun email n'est envoyé si une collection est la première à être en rang 1.
        """
        self._position_collection(self.collection1, 1, self.instructor1)
        self.assertEqual(self.resource.arbitration, Arbitration.NONE)
        self.assertEqual(len(mail.outbox), 0)

    # --- SUPPRESSION ---
    # Le test 'test_no_email_if_notification_settings_are_off' est supprimé car non pertinent pour l'instant.

    def test_no_email_for_non_rank_1_positioning(self):
        """
        Vérifie qu'aucun email n'est envoyé pour des positionnements autres que le rang 1.
        """
        self._position_collection(self.collection1, 2, self.instructor1)
        mail.outbox = []
        self._position_collection(self.collection2, 2, self.instructor2)
        self.assertEqual(self.resource.arbitration, Arbitration.NONE)
        self.assertEqual(len(mail.outbox), 0)
