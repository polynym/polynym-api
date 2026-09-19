from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from identity.models import CallerRole, Identity, Person, RolePolicy


User = get_user_model()

class AcceptLanguageTests(APITestCase):
    """Content negotiation: where a person holds several records of one
    type in different languages, the caller's Accept-Language header
    selects the best match (Persona 2, Jenny Chen)."""

    def setUp(self):
        self.person = Person.objects.create(email="jenny.chen@example.com")

        # Two legal-name records differing only by language.
        Identity.objects.create(
            person=self.person,
            type="legal",
            value="Jenny Chen",
            context_tag="legal",
            language_code="en",
        )
        Identity.objects.create(
            person=self.person,
            type="legal",
            value="陳",
            context_tag="legal",
            language_code="zh",
        )

        RolePolicy.objects.create(
            role="hr", allowed_types=["legal"], writable_types=["legal"]
        )

        self.user = User.objects.create_user(
            username="hr_caller", password="testpass123"
        )
        CallerRole.objects.create(
            user=self.user, caller_name="HR system", role="hr"
        )

        self.url = reverse(
            "person-identity-detail",
            kwargs={"person_id": self.person.id},
        )

    def authenticate(self):
        access = RefreshToken.for_user(self.user).access_token
        access["role"] = "hr"
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def _legal_values(self, response):
        return [
            item["value"]
            for item in response.data["identities"]
            if item["type"] == "legal"
        ]

    def test_chinese_preference_returns_chinese_record(self):
        self.authenticate()
        response = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE="zh")

        self.assertEqual(self._legal_values(response), ["陳"])

    def test_english_preference_returns_english_record(self):
        self.authenticate()
        response = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE="en")

        self.assertEqual(self._legal_values(response), ["Jenny Chen"])

    def test_quality_values_are_respected(self):
        self.authenticate()
        response = self.client.get(
            self.url, HTTP_ACCEPT_LANGUAGE="en;q=0.4, zh;q=0.9"
        )

        self.assertEqual(self._legal_values(response), ["陳"])

    def test_no_preference_falls_back_to_a_single_record(self):
        self.authenticate()
        response = self.client.get(self.url)

        # No header: exactly one legal name is returned, not both.
        self.assertEqual(len(self._legal_values(response)), 1)

    def test_unsupported_language_falls_back_to_a_single_record(self):
        self.authenticate()
        response = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE="fr")

        self.assertEqual(len(self._legal_values(response)), 1)
        
        
