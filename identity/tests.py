from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import CallerRole, Identity, Person, RolePolicy


User = get_user_model()


class RBACIdentityFilteringTests(APITestCase):
    def setUp(self):
        self.person = Person.objects.create(email="maya@example.com")

        Identity.objects.create(
            person=self.person,
            type="legal",
            value="Maria Thompson",
            context_tag="legal",
            language_code="en",
            script_code="",
        )

        Identity.objects.create(
            person=self.person,
            type="chosen",
            value="Maya",
            context_tag="public",
            language_code="en",
            script_code="",
        )

        Identity.objects.create(
            person=self.person,
            type="username",
            value="maya_codes",
            context_tag="online",
            language_code="en",
            script_code="",
        )

        RolePolicy.objects.create(
            role="self",
            allowed_types=[
                "legal",
                "chosen",
                "preferred",
                "religious",
                "professional",
                "username",
            ],
        )

        RolePolicy.objects.create(
            role="hr",
            allowed_types=["legal"],
        )

        RolePolicy.objects.create(
            role="public",
            allowed_types=["chosen", "preferred"],
        )

        self.self_user = User.objects.create_user(
            username="maya_self",
            password="testpass123",
        )

        CallerRole.objects.create(
            user=self.self_user,
            person=self.person,
            caller_name="Maya self account",
            role="self",
        )

        self.hr_user = User.objects.create_user(
            username="hr_user",
            password="testpass123",
        )

        CallerRole.objects.create(
            user=self.hr_user,
            caller_name="HR system",
            role="hr",
        )

        self.public_user = User.objects.create_user(
            username="public_user",
            password="testpass123",
        )

        CallerRole.objects.create(
            user=self.public_user,
            caller_name="Public caller",
            role="public",
        )

        self.url = reverse(
            "person-identity-detail",
            kwargs={"person_id": self.person.id},
        )

    def authenticate_as(self, user):
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token
        access["role"] = user.caller_role.role

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(access)}"
        )

    def test_hr_role_only_receives_legal_name(self):
        self.authenticate_as(self.hr_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_types = {
            item["type"] for item in response.data["identities"]
        }

        self.assertIn("legal", returned_types)
        self.assertNotIn("chosen", returned_types)
        self.assertNotIn("username", returned_types)
        self.assertNotIn("email", response.data)

    def test_public_role_receives_chosen_name_only(self):
        self.authenticate_as(self.public_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_types = {
            item["type"] for item in response.data["identities"]
        }

        self.assertIn("chosen", returned_types)
        self.assertNotIn("legal", returned_types)
        self.assertNotIn("username", returned_types)
        self.assertNotIn("email", response.data)

    def test_self_role_receives_full_identity_access(self):
        self.authenticate_as(self.self_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_types = {
            item["type"] for item in response.data["identities"]
        }

        self.assertIn("legal", returned_types)
        self.assertIn("chosen", returned_types)
        self.assertIn("username", returned_types)
        self.assertIn("email", response.data)

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)