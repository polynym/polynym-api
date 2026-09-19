from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from identity.models import AuditLog, Identity, Person

from .fixtures import PolicyFixtureMixin


class ErasureTests(PolicyFixtureMixin, APITestCase):
    """GDPR Article 17: the data subject may erase their own record, and
    no identity data survives the request."""

    def setUp(self):
        self.build_fixtures()
        self.erasure_url = reverse(
            "person-erasure", kwargs={"person_id": self.person.id}
        )

    def test_self_can_erase_own_record(self):
        self.authenticate_as(self.users["self"])
        response = self.client.delete(self.erasure_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_no_identity_data_survives_erasure(self):
        self.authenticate_as(self.users["self"])
        self.client.delete(self.erasure_url)

        self.assertFalse(Person.objects.filter(id=self.person.id).exists())
        self.assertEqual(Identity.objects.filter(person_id=self.person.id).count(), 0)

    def test_erased_record_is_no_longer_retrievable(self):
        self.authenticate_as(self.users["self"])
        self.client.delete(self.erasure_url)

        self.authenticate_as(self.users["hr"])
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_hr_cannot_erase_a_person(self):
        self.authenticate_as(self.users["hr"])
        response = self.client.delete(self.erasure_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Person.objects.filter(id=self.person.id).exists())

    def test_self_cannot_erase_another_persons_record(self):
        other = Person.objects.create(email="other@example.com")
        other_url = reverse("person-erasure", kwargs={"person_id": other.id})

        self.authenticate_as(self.users["self"])
        response = self.client.delete(other_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Person.objects.filter(id=other.id).exists())

    def test_unauthenticated_erasure_is_rejected(self):
        response = self.client.delete(self.erasure_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(Person.objects.filter(id=self.person.id).exists())

    def test_audit_entry_survives_erasure_without_personal_data(self):
        """The audit trail must evidence that erasure occurred while no
        longer referencing the erased person."""
        self.authenticate_as(self.users["self"])
        self.client.delete(self.erasure_url)

        entry = AuditLog.objects.latest("timestamp")

        self.assertEqual(entry.action, "DELETE")
        self.assertEqual(entry.caller_role, "self")
        self.assertIsNone(entry.person)
        self.assertIn("legal", entry.fields_returned)
