"""Tests fo access to identify data after erasure.

JWT access tokens remain valid after erasure because they are stateless.
Access is prevented at the data layer because the person's records no
longer exists. These tests verify that credentials issued before erasure
cannot retrieve the erased identity data.
"""

from rest_framework.test import APITestCase

from identity.tests.fixtures import PolicyFixtureMixin


class TokenInvalidationAfterErasureTests(PolicyFixtureMixin, APITestCase):
    """Test access using credentials issued before a person's erasure."""
    
    def setUp(self):
        """Create the shared test fixtures."""
        self.build_fixtures()

    def test_pre_erasure_self_token_retrieves_nothing_after_erasure(self):
        """A self token cannot retrieve a person record after easure."""
        self.authenticate_as(self.users["self"])

        before = self.client.get(self.url)
        self.assertEqual(before.status_code, 200)

        erase = self.client.delete(f"/api/persons/{self.person.id}/")
        self.assertEqual(erase.status_code, 204)

        after = self.client.get(self.url)
        self.assertEqual(after.status_code, 404)

    def test_pre_erasure_hr_token_retrieves_nothing_after_erasure(self):
        """An HR token cannot retrieve a person record after easure."""
        self.authenticate_as(self.users["hr"])

        before = self.client.get(self.url)
        self.assertEqual(before.status_code, 200)

        self.authenticate_as(self.users["self"])
        erase = self.client.delete(f"/api/persons/{self.person.id}/")
        self.assertEqual(erase.status_code, 204)

        self.authenticate_as(self.users["hr"])
        after = self.client.get(self.url)
        self.assertEqual(after.status_code, 404)