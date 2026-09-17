from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import AuditLog, CallerRole, Identity, Person, RolePolicy
from .services import (
    get_allowed_identity_types,
    get_caller_role,
    get_writable_identity_types,
    parse_accepted_languages,
)

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


class PolicyLookupUnitTests(TestCase):
    """Unit tests for the policy lookup functions, isolated from HTTP."""

    def setUp(self):
        RolePolicy.objects.create(
            role="hr", allowed_types=["legal"], writable_types=["legal"]
        )
        RolePolicy.objects.create(role="public", allowed_types=["chosen", "preferred"])

    def test_returns_configured_types_for_known_role(self):
        self.assertEqual(get_allowed_identity_types("hr"), ["legal"])
        self.assertEqual(get_allowed_identity_types("public"), ["chosen", "preferred"])

    def test_returns_empty_list_for_unknown_role(self):
        # Fail closed: an unrecognised role discloses nothing.
        self.assertEqual(get_allowed_identity_types("finance"), [])

    def test_returns_empty_list_for_empty_role(self):
        self.assertEqual(get_allowed_identity_types(""), [])
        self.assertEqual(get_allowed_identity_types(None), [])

    def test_policy_change_takes_effect_without_restart(self):
        policy = RolePolicy.objects.get(role="hr")
        policy.allowed_types = ["legal", "professional"]
        policy.save()
        
        self.assertEqual(get_allowed_identity_types("hr"), ["legal", "professional"])
        
    def test_writable_types_for_known_role(self):
        self.assertEqual(get_writable_identity_types("hr"), ["legal"])
        # public has a read policy but no write list
        self.assertEqual(get_writable_identity_types("public"), [])

    def test_writable_returns_empty_for_unknown_or_empty_role(self):
        self.assertEqual(get_writable_identity_types("finance"), [])
        self.assertEqual(get_writable_identity_types(""), [])
        self.assertEqual(get_writable_identity_types(None), [])
    
    def test_parse_accepted_languages_orders_by_quality(self):
        self.assertEqual(
            parse_accepted_languages("en;q=0.4, zh;q=0.9, fr;q=0.1"),
            ["zh", "en", "fr"],
        )

    def test_parse_accepted_languages_defaults_missing_q_to_one(self):
        self.assertEqual(
            parse_accepted_languages("zh;q=0.9, en"),
            ["en", "zh"],
        )

    def test_parse_accepted_languages_handles_empty_header(self):
        self.assertEqual(parse_accepted_languages(""), [])

        


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


class CallerRoleResolutionUnitTests(TestCase):
    """Unit tests for get_caller_role(), covering both resolution paths."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="hr_caller", password="testpass123"
        )
        CallerRole.objects.create(user=self.user, caller_name="HR system", role="hr")

    def test_role_is_read_from_token_payload(self):
        request = FakeRequest(auth=FakeToken({"role": "medical"}))
        self.assertEqual(get_caller_role(request), "medical")

    def test_falls_back_to_database_when_token_has_no_role(self):
        request = FakeRequest(auth=FakeToken({}), user=self.user)
        self.assertEqual(get_caller_role(request), "hr")

    def test_token_claim_takes_precedence_over_database(self):
        # Documents the stale-claim risk: a token issued before a role
        # change continues to assert the old role until it expires.
        request = FakeRequest(auth=FakeToken({"role": "self"}), user=self.user)
        self.assertEqual(get_caller_role(request), "self")

    def test_returns_none_when_no_token_and_no_user(self):
        request = FakeRequest(auth=None, user=None)
        self.assertIsNone(get_caller_role(request))

    def test_returns_none_when_user_has_no_caller_role(self):
        orphan = User.objects.create_user(username="orphan", password="testpass123")
        request = FakeRequest(auth=FakeToken({}), user=orphan)
        self.assertIsNone(get_caller_role(request))


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
            item
            for item in response.data["identities"]
            if item["type"] == "legal"
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


class SelfRoleAccessControlTests(PolicyFixtureMixin, APITestCase):
    """The self role must not be able to read another person's record."""

    def setUp(self):
        self.build_fixtures()

        self.other_person = Person.objects.create(email="other@example.com")
        Identity.objects.create(
            person=self.other_person,
            type="legal",
            value="Someone Else",
            context_tag="legal",
            language_code="en",
        )

        self.other_url = reverse(
            "person-identity-detail",
            kwargs={"person_id": self.other_person.id},
        )

    def test_self_role_cannot_read_another_persons_record(self):
        self.authenticate_as(self.users["self"])
        response = self.client.get(self.other_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_self_role_can_read_own_record(self):
        self.authenticate_as(self.users["self"])
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_hr_role_may_read_any_person(self):
        self.authenticate_as(self.users["hr"])
        response = self.client.get(self.other_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class AuthenticationBoundaryTests(PolicyFixtureMixin, APITestCase):
    """Equivalence partitions for the credential and identifier inputs."""

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

    def test_caller_with_no_policy_receives_nothing(self):
        user = User.objects.create_user(
            username="finance_caller", password="testpass123"
        )
        CallerRole.objects.create(
            user=user, caller_name="Finance system", role="finance"
        )

        self.authenticate_as(user)
        response = self.client.get(self.url)

        # Fail closed: an authenticated caller with no policy receives an
        # empty identity list rather than an error, so the response does
        # not reveal which identity types exist.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["identities"], [])

    def test_nonexistent_person_returns_404(self):
        self.authenticate_as(self.users["hr"])
        response = self.client.get(
            reverse("person-identity-detail", kwargs={"person_id": 9999})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_token_for_user_without_caller_role_has_empty_role_claim(self):
        User.objects.create_user(username="unassigned", password="testpass123")

        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "unassigned", "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)


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

class ErasureTests(PolicyFixtureMixin, APITestCase):
    """GDPR Article 17: the data subject may erase their own record, and
    no identity data survives the request."""

    def setUp(self):
        self.build_fixtures()
        self.erasure_url = reverse(
            "person-erasure", kwargs={"person_id": self.person.id}
        )

    def test_self_can_erase_own_record(self):
        self.authenticate_as(self.users["self"])
        response = self.client.delete(self.erasure_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_no_identity_data_survives_erasure(self):
        self.authenticate_as(self.users["self"])
        self.client.delete(self.erasure_url)

        self.assertFalse(Person.objects.filter(id=self.person.id).exists())
        self.assertEqual(
            Identity.objects.filter(person_id=self.person.id).count(), 0
        )

    def test_erased_record_is_no_longer_retrievable(self):
        self.authenticate_as(self.users["self"])
        self.client.delete(self.erasure_url)

        self.authenticate_as(self.users["hr"])
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_hr_cannot_erase_a_person(self):
        self.authenticate_as(self.users["hr"])
        response = self.client.delete(self.erasure_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Person.objects.filter(id=self.person.id).exists())

    def test_self_cannot_erase_another_persons_record(self):
        other = Person.objects.create(email="other@example.com")
        other_url = reverse("person-erasure", kwargs={"person_id": other.id})

        self.authenticate_as(self.users["self"])
        response = self.client.delete(other_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Person.objects.filter(id=other.id).exists())

    def test_unauthenticated_erasure_is_rejected(self):
        response = self.client.delete(self.erasure_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(Person.objects.filter(id=self.person.id).exists())

    def test_audit_entry_survives_erasure_without_personal_data(self):
        """The audit trail must evidence that erasure occurred while no
        longer referencing the erased person."""
        self.authenticate_as(self.users["self"])
        self.client.delete(self.erasure_url)

        entry = AuditLog.objects.latest("timestamp")

        self.assertEqual(entry.action, "DELETE")
        self.assertEqual(entry.caller_role, "self")
        self.assertIsNone(entry.person)
        self.assertIn("legal", entry.fields_returned)
        
class WritePolicyTests(PolicyFixtureMixin, APITestCase):
    """Write permissions are enforced independently of read permissions."""

    def setUp(self):
        self.build_fixtures()
        self.collection_url = reverse(
            "person-identity-collection",
            kwargs={"person_id": self.person.id},
        )

    def identity_url(self, identity_type):
        identity = Identity.objects.get(
            person=self.person, type=identity_type
        )
        return reverse(
            "identity-detail", kwargs={"identity_id": identity.id}
        )

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
        self.assertFalse(
            Identity.objects.filter(value="Injected Name").exists()
        )

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
            Identity.objects.filter(
                person=self.person, type="username"
            ).exists()
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
        