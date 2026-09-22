from django.contrib.auth import get_user_model
from django.test import TestCase

from identity.models import CallerRole, RolePolicy
from identity.services import (
    get_allowed_identity_types,
    get_caller_role,
    get_writable_identity_types,
    parse_accepted_languages,
)

from .fixtures import FakeRequest, FakeToken

User = get_user_model()


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

    def test_parse_accepted_languages_tolerates_malformed_quality(self):
        self.assertEqual(parse_accepted_languages("zh;q=abc"), ["zh"])

    def test_parse_accepted_languages_skips_empty_entries(self):
        self.assertEqual(parse_accepted_languages("en,,zh"), ["en", "zh"])


class CallerRoleResolutionUnitTests(TestCase):
    """Unit tests for database-backed caller role resolution."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="hr_caller",
            password="testpass123",
        )
        CallerRole.objects.create(
            user=self.user,
            caller_name="HR system",
            role="hr",
        )

    def test_role_is_read_from_database(self):
        """The caller role is read from the user's CallerRole record."""
        request = FakeRequest(auth=None, user=self.user)

        self.assertEqual(get_caller_role(request), "hr")

    def test_token_role_does_not_override_database_role(self):
        """A role stored in a token does not override the current database role."""
        request = FakeRequest(
            auth=FakeToken({"role": "self"}),
            user=self.user,
        )

        self.assertEqual(get_caller_role(request), "hr")

    def test_database_role_change_takes_effect(self):
        """A change to the stored caller role is used on later requests."""
        caller_role = CallerRole.objects.get(user=self.user)
        caller_role.role = "public"
        caller_role.save()

        refreshed_user = User.objects.get(pk=self.user.pk)
        request = FakeRequest(
            auth=FakeToken({"role": "hr"}),
            user=refreshed_user,
        )

        self.assertEqual(get_caller_role(request), "public")

    def test_returns_none_when_no_token_and_no_user(self):
        """A request without an authenticated user has no caller role."""
        request = FakeRequest(auth=None, user=None)

        self.assertIsNone(get_caller_role(request))

    def test_returns_none_when_user_has_no_caller_role(self):
        """An authenticated user without a CallerRole has no caller role."""
        orphan = User.objects.create_user(
            username="orphan",
            password="testpass123",
        )
        request = FakeRequest(auth=FakeToken({}), user=orphan)

        self.assertIsNone(get_caller_role(request))
