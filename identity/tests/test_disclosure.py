from rest_framework import status
from rest_framework.test import APITestCase

from .fixtures import (
    ALL_TYPES,
    POLICY_MATRIX,
    ZOE_IDENTITIES,
    PolicyFixtureMixin,
)


class DecisionTableDisclosureTests(PolicyFixtureMixin, APITestCase):
    """Exhaustive role x identity-type coverage: every cell of the policy
    matrix is asserted as either permitted or denied."""

    def setUp(self):
        self.build_fixtures()

    def test_every_matrix_cell_behaves_as_specified(self):
        for role, allowed in POLICY_MATRIX.items():
            with self.subTest(role=role):
                self.authenticate_as(self.users[role])
                response = self.client.get(self.url)

                self.assertEqual(response.status_code, status.HTTP_200_OK)

                returned = {item["type"] for item in response.data["identities"]}

                for identity_type in ALL_TYPES:
                    if identity_type in allowed:
                        self.assertIn(
                            identity_type,
                            returned,
                            f"{role} should receive {identity_type}",
                        )
                    else:
                        self.assertNotIn(
                            identity_type,
                            returned,
                            f"{role} must not receive {identity_type}",
                        )

    def test_hr_receives_legal_name_value(self):
        self.authenticate_as(self.users["hr"])
        response = self.client.get(self.url)

        legal = next(
            item for item in response.data["identities"] if item["type"] == "legal"
        )

        self.assertEqual(legal["value"], ZOE_IDENTITIES["legal"])

    def test_public_caller_never_receives_birth_name(self):
        """The clinical motivation in the design chapter depends on this:
        a public caller must not surface the legal name."""
        self.authenticate_as(self.users["public"])
        response = self.client.get(self.url)

        values = {item["value"] for item in response.data["identities"]}

        self.assertIn(ZOE_IDENTITIES["chosen"], values)
        self.assertNotIn(ZOE_IDENTITIES["legal"], values)

    def test_email_is_disclosed_only_to_self(self):
        for role in POLICY_MATRIX:
            with self.subTest(role=role):
                self.authenticate_as(self.users[role])
                response = self.client.get(self.url)

                if role == "self":
                    self.assertIn("email", response.data)
                else:
                    self.assertNotIn("email", response.data)
