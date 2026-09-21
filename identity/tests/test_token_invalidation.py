"""Token invalidation after erasure.

The project's evaluation plan includes privacy-aware deletion and
token invalidation tests: a credential issued before an erasure must
not be able to retrieve identity data afterwards. Access tokens are
stateless JWTs, so the guarantee is enforced at the data layer (the
records are gone) rather than by a token blocklist. These tests
verify that guarantee from the caller's perspective.
"""

from rest_framework.test import APITestCase

from identity.tests.fixtures import PolicyFixtureMixin


class TokenInvalidationAfterErasureTests(PolicyFixtureMixin, APITestCase):
    def setUp(self):
        self.build_fixtures()

    def test_pre_erasure_self_token_retrieves_nothing_after_erasure(self):
        # Authenticate as the data subject BEFORE erasure; this token
        # stays attached to the client for the whole test.
        self.authenticate_as(self.users["self"])

        # Sanity: the token works while the record exists.
        before = self.client.get(self.url)
        self.assertEqual(before.status_code, 200)

        # The data subject erases their record.
        erase = self.client.delete(f"/api/persons/{self.person.id}/")
        self.assertEqual(erase.status_code, 204)

        # The same, still-valid token can no longer retrieve anything.
        after = self.client.get(self.url)
        self.assertEqual(after.status_code, 404)

    def test_pre_erasure_hr_token_retrieves_nothing_after_erasure(self):
        # A third-party (hr) token issued before erasure is equally
        # unable to reach the erased record afterwards.
        self.authenticate_as(self.users["hr"])

        before = self.client.get(self.url)
        self.assertEqual(before.status_code, 200)

        # Erasure is performed by the data subject...
        self.authenticate_as(self.users["self"])
        erase = self.client.delete(f"/api/persons/{self.person.id}/")
        self.assertEqual(erase.status_code, 204)

        # ...and the hr caller, re-presenting their earlier credential,
        # receives 404.
        self.authenticate_as(self.users["hr"])
        after = self.client.get(self.url)
        self.assertEqual(after.status_code, 404)