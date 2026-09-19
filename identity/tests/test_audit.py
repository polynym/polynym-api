from django.urls import reverse
from rest_framework.test import APITestCase

from identity.models import AuditLog, Identity, Person

from .fixtures import PolicyFixtureMixin


class AuditLogTests(PolicyFixtureMixin, APITestCase):
    """GDPR Article 5(2) accountability: every disclosure must be recorded,
    and the record must reflect what was actually disclosed."""

    def setUp(self):
        self.build_fixtures()

    def test_successful_request_creates_audit_entry(self):
        self.authenticate_as(self.users["hr"])
        self.client.get(self.url)

        entry = AuditLog.objects.latest("timestamp")

        self.assertEqual(entry.person, self.person)
        self.assertEqual(entry.caller_role, "hr")
        self.assertEqual(entry.action, "GET")

    def test_unauthenticated_request_creates_no_audit_entry(self):
        self.client.get(self.url)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_audit_records_types_actually_returned(self):
        """A caller whose policy permits a type the person does not hold
        must not be logged as having received it."""
        sparse_person = Person.objects.create(email="sparse@example.com")
        Identity.objects.create(
            person=sparse_person,
            type="legal",
            value="Only A Legal Name",
            context_tag="legal",
            language_code="en",
        )

        self.authenticate_as(self.users["medical"])
        self.client.get(
            reverse(
                "person-identity-detail",
                kwargs={"person_id": sparse_person.id},
            )
        )

        entry = AuditLog.objects.latest("timestamp")

        # The medical role is permitted legal and chosen, but this person
        # holds only a legal name, so only legal was actually disclosed.
        self.assertEqual(entry.fields_returned, ["legal"])
