from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from identity.models import AuditLog, Identity, Person

from .fixtures import ALL_TYPES, WRITE_MATRIX, PolicyFixtureMixin


class WritePolicyTests(PolicyFixtureMixin, APITestCase):
    """Write permissions are enforced independently of read permissions."""

    def setUp(self):
        self.build_fixtures()
        self.collection_url = reverse(
            "person-identity-collection",
            kwargs={"person_id": self.person.id},
        )

    def identity_url(self, identity_type):
        identity = Identity.objects.get(person=self.person, type=identity_type)
        return reverse("identity-detail", kwargs={"identity_id": identity.id})

    def test_every_write_matrix_cell_behaves_as_specified(self):
        for role, writable in WRITE_MATRIX.items():
            for identity_type in ALL_TYPES:
                with self.subTest(role=role, type=identity_type):
                    self.authenticate_as(self.users[role])

                    response = self.client.put(
                        self.identity_url(identity_type),
                        {
                            "type": identity_type,
                            "value": "Updated Value",
                            "context_tag": identity_type,
                            "language_code": "en",
                            "script_code": "",
                        },
                        format="json",
                    )

                    if identity_type in writable:
                        self.assertEqual(
                            response.status_code,
                            status.HTTP_200_OK,
                            f"{role} should be able to write {identity_type}",
                        )
                    else:
                        self.assertEqual(
                            response.status_code,
                            status.HTTP_403_FORBIDDEN,
                            f"{role} must not write {identity_type}",
                        )

    def test_self_can_create_an_identity(self):
        Identity.objects.get(person=self.person, type="preferred").delete()

        self.authenticate_as(self.users["self"])

        response = self.client.post(
            self.collection_url,
            {
                "type": "preferred",
                "value": "Zo",
                "context_tag": "informal",
                "language_code": "en",
                "script_code": "",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Identity.objects.filter(person=self.person, value="Zo").exists()
        )

    def test_public_caller_cannot_create_an_identity(self):
        self.authenticate_as(self.users["public"])

        response = self.client.post(
            self.collection_url,
            {
                "type": "chosen",
                "value": "Injected Name",
                "context_tag": "public",
                "language_code": "en",
                "script_code": "",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Identity.objects.filter(value="Injected Name").exists())

    def test_read_permission_does_not_imply_write_permission(self):
        """The medical role may read a chosen name but must not change it."""
        self.authenticate_as(self.users["medical"])

        read = self.client.get(self.url)
        returned = {item["type"] for item in read.data["identities"]}
        self.assertIn("chosen", returned)

        write = self.client.put(
            self.identity_url("chosen"),
            {
                "type": "chosen",
                "value": "Changed By Clinician",
                "context_tag": "public",
                "language_code": "en",
                "script_code": "",
            },
            format="json",
        )

        self.assertEqual(write.status_code, status.HTTP_403_FORBIDDEN)

    def test_caller_cannot_relabel_a_record_into_a_forbidden_type(self):
        """An hr caller may write legal names, but must not convert a
        legal record into a chosen one to escape its policy."""
        self.authenticate_as(self.users["hr"])

        response = self.client.put(
            self.identity_url("legal"),
            {
                "type": "chosen",
                "value": "Escalated",
                "context_tag": "public",
                "language_code": "en",
                "script_code": "",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Identity.objects.filter(value="Escalated").exists())

    def test_self_cannot_write_to_another_persons_record(self):
        other = Person.objects.create(email="other@example.com")
        other_identity = Identity.objects.create(
            person=other,
            type="legal",
            value="Someone Else",
            context_tag="legal",
            language_code="en",
        )

        self.authenticate_as(self.users["self"])

        response = self.client.put(
            reverse(
                "identity-detail",
                kwargs={"identity_id": other_identity.id},
            ),
            {
                "type": "legal",
                "value": "Hijacked",
                "context_tag": "legal",
                "language_code": "en",
                "script_code": "",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_self_can_delete_a_single_identity(self):
        self.authenticate_as(self.users["self"])

        response = self.client.delete(self.identity_url("username"))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Identity.objects.filter(person=self.person, type="username").exists()
        )

    def test_write_is_recorded_in_the_audit_log(self):
        self.authenticate_as(self.users["self"])

        self.client.put(
            self.identity_url("preferred"),
            {
                "type": "preferred",
                "value": "Zo",
                "context_tag": "informal",
                "language_code": "en",
                "script_code": "",
            },
            format="json",
        )

        entry = AuditLog.objects.latest("timestamp")

        self.assertEqual(entry.action, "PUT")
        self.assertEqual(entry.caller_role, "self")
        self.assertEqual(entry.fields_returned, ["preferred"])

    def test_unauthenticated_write_is_rejected(self):
        response = self.client.put(
            self.identity_url("legal"),
            {
                "type": "legal",
                "value": "Anonymous Edit",
                "context_tag": "legal",
                "language_code": "en",
                "script_code": "",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
