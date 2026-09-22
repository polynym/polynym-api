from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from identity.models import CallerRole

from .fixtures import PolicyFixtureMixin

User = get_user_model()


class AuthenticationBoundaryTests(PolicyFixtureMixin, APITestCase):
    """Test authentication and access boundary conditions."""

    def setUp(self):
        self.build_fixtures()

    def test_request_without_token_is_rejected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_malformed_token_is_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_endpoint_issues_access_and_refresh_tokens(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "hr_caller", "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_wrong_password_does_not_issue_token(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "hr_caller", "password": "wrong"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_caller_with_no_policy_is_rejected(self):
        """A caller without a configured role policy is rejected."""
        user = User.objects.create_user(
        username="finance_caller",
        password="testpass123",
        )
        CallerRole.objects.create(
        user=user,
        caller_name="Finance system",
        role="finance",
        )

        self.authenticate_as(user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_nonexistent_person_returns_404(self):
        self.authenticate_as(self.users["hr"])
        response = self.client.get(
            reverse("person-identity-detail", kwargs={"person_id": 9999})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_token_for_user_without_caller_role_has_empty_role_claim(self):
        """A user without a caller role can still obtain a token."""
        User.objects.create_user(username="unassigned", password="testpass123")

        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "unassigned", "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
