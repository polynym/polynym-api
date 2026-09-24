"""Tests for access to identity data after erasure.

JWT access tokens remain valid after erasure because they are stateless.
The person and identity records are deleted, so credentials issued before
erasure can no longer retrieve the erased identity data.
"""

from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from identity.tests.fixtures import PolicyFixtureMixin


class AccessAfterErasureTests(PolicyFixtureMixin, APITestCase):
    """Test access using credentials issued before a person's erasure."""

    def setUp(self):
        """Create the users, identities, roles, and policies used in each test."""
        self.build_fixtures()

    def test_pre_erasure_self_token_retrieves_nothing_after_erasure(self):
        """A self token cannot retrieve a person record after erasure."""
        self.authenticate_as(self.users["self"])

        before = self.client.get(self.url)
        self.assertEqual(before.status_code, 200)

        erase = self.client.delete(f"/api/persons/{self.person.id}/")
        self.assertEqual(erase.status_code, 204)

        after = self.client.get(self.url)
        self.assertEqual(after.status_code, 404)

    def test_pre_erasure_hr_token_retrieves_nothing_after_erasure(self):
        """An HR token issued before erasure cannot retrieve the erased record."""
        hr_access = RefreshToken.for_user(self.users["hr"]).access_token

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {hr_access}")
        before = self.client.get(self.url)
        self.assertEqual(before.status_code, 200)

        self.authenticate_as(self.users["self"])
        erase = self.client.delete(f"/api/persons/{self.person.id}/")
        self.assertEqual(erase.status_code, 204)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {hr_access}")
        after = self.client.get(self.url)
        self.assertEqual(after.status_code, 404)
