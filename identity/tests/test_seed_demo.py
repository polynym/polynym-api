import os
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from identity.models import CallerRole, Identity, Person, RolePolicy

User = get_user_model()

DEMO_PASSWORDS = {
    "DEMO_SELF_PASSWORD": "self-test-password",
    "DEMO_HR_PASSWORD": "hr-test-password",
    "DEMO_PUBLIC_PASSWORD": "public-test-password",
    "DEMO_MEDICAL_PASSWORD": "medical-test-password",
}


def run_seed():
    """Run the seed_demo command and return its output."""
    out = StringIO()

    with patch.dict(os.environ, DEMO_PASSWORDS):
        call_command("seed_demo", stdout=out)

    return out.getvalue()


class SeedDemoCommandTests(TestCase):
    """Test creation and repeatability of the seeded demonstration data."""

    def test_creates_the_demo_person_with_all_identity_types(self):
        """The seeded person has all six supported identity types."""
        run_seed()

        person = Person.objects.get(email="zoe.taylor@example.com")

        self.assertEqual(person.identities.count(), 6)
        self.assertSetEqual(
            set(person.identities.values_list("type", flat=True)),
            {
                "legal",
                "chosen",
                "preferred",
                "professional",
                "religious",
                "username",
            },
        )

    def test_creates_all_four_role_policies_with_write_lists(self):
        """The seed command creates the four configured role policies."""
        run_seed()

        self.assertEqual(RolePolicy.objects.count(), 4)

        hr = RolePolicy.objects.get(role="hr")
        public = RolePolicy.objects.get(role="public")

        self.assertEqual(hr.writable_types, ["legal"])
        self.assertEqual(public.writable_types, [])

    def test_creates_caller_accounts_and_links_only_self_to_person(self):
        """Only the self caller account is linked to the person record."""
        run_seed()

        self.assertEqual(CallerRole.objects.count(), 4)

        zoe = CallerRole.objects.get(user__username="zoe_self")
        hr = CallerRole.objects.get(user__username="hr_user")

        self.assertIsNotNone(zoe.person)
        self.assertIsNone(hr.person)

    def test_seeded_credentials_can_authenticate(self):
        """Seeded caller credentials can obtain a JWT."""
        run_seed()

        response = self.client.post(
            "/api/token/",
            {
                "username": "hr_user",
                "password": DEMO_PASSWORDS["DEMO_HR_PASSWORD"],
            },
        )

        self.assertEqual(response.status_code, 200)

    def test_running_twice_creates_no_duplicates(self):
        """Running the seed command twice does not create duplicates."""
        run_seed()
        run_seed()

        self.assertEqual(Person.objects.count(), 1)
        self.assertEqual(Identity.objects.count(), 6)
        self.assertEqual(RolePolicy.objects.count(), 4)
        self.assertEqual(User.objects.count(), 4)

    def test_missing_demo_passwords_prevent_seeding(self):
        """Missing demo password variables prevent partial seed data creation."""
        missing_passwords = {name: "" for name in DEMO_PASSWORDS}

        with (
            patch.dict(os.environ, missing_passwords),
            self.assertRaises(CommandError),
        ):
            call_command("seed_demo")

        self.assertEqual(Person.objects.count(), 0)
        self.assertEqual(User.objects.count(), 0)
