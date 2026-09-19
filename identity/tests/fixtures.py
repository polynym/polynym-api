from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken

from identity.models import CallerRole, Identity, Person, RolePolicy

User = get_user_model()
# The policy matrix under test. Every cell of role x identity type is a
# test case, which gives exhaustive coverage of the disclosure decision.
POLICY_MATRIX = {
    "self": [
        "legal",
        "chosen",
        "preferred",
        "professional",
        "religious",
        "username",
    ],
    "hr": ["legal"],
    "public": ["chosen", "preferred"],
    "medical": ["legal", "chosen"],
}

WRITE_MATRIX = {
    "self": [
        "legal",
        "chosen",
        "preferred",
        "professional",
        "religious",
        "username",
    ],
    "hr": ["legal"],
    "public": [],
    "medical": [],
}

ALL_TYPES = [
    "legal",
    "chosen",
    "preferred",
    "professional",
    "religious",
    "username",
]

# Test record for Persona 1 (Zoe), matching seed_demo.
ZOE_IDENTITIES = {
    "legal": "Sebastian Taylor",
    "chosen": "Zoe Taylor",
    "preferred": "Zoe",
    "professional": "Dr Zoe Taylor",
    "religious": "Zoe Maria",
    "username": "zoe_codes",
}


class PolicyFixtureMixin:
    """One person holding every identity type, plus one authenticated
    caller account for each role in the policy matrix."""

    def build_fixtures(self):
        self.person = Person.objects.create(email="zoe.taylor@example.com")

        for identity_type, value in ZOE_IDENTITIES.items():
            Identity.objects.create(
                person=self.person,
                type=identity_type,
                value=value,
                context_tag=identity_type,
                language_code="en",
            )

        for role, allowed in POLICY_MATRIX.items():
            RolePolicy.objects.create(
                role=role,
                allowed_types=allowed,
                writable_types=WRITE_MATRIX[role],
            )

        self.users = {}

        for role in POLICY_MATRIX:
            user = User.objects.create_user(
                username=f"{role}_caller",
                password="testpass123",
            )

            CallerRole.objects.create(
                user=user,
                person=self.person if role == "self" else None,
                caller_name=f"{role} caller",
                role=role,
            )

            self.users[role] = user

        self.url = reverse(
            "person-identity-detail",
            kwargs={"person_id": self.person.id},
        )

    def authenticate_as(self, user):
        access = RefreshToken.for_user(user).access_token
        access["role"] = user.caller_role.role
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")


class FakeToken:
    """Minimal stand-in for a validated simplejwt token."""

    def __init__(self, payload):
        self.payload = payload

    def get(self, key, default=None):
        return self.payload.get(key, default)


class FakeRequest:
    def __init__(self, auth=None, user=None):
        self.auth = auth
        self.user = user
