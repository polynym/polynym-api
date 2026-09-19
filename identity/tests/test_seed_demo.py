from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from identity.models import CallerRole, Identity, Person, RolePolicy


User = get_user_model()


def run_seed():
    out = StringIO()
    call_command("seed_demo", stdout=out)
    return out.getvalue()


class SeedDemoCommandTests(TestCase):
    """The seed command builds the complete demonstration world, and
    running it repeatedly is harmless."""

    def test_creates_the_demo_person_with_all_identity_types(self):
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
        run_seed()

        self.assertEqual(RolePolicy.objects.count(), 4)

        hr = RolePolicy.objects.get(role="hr")
        public = RolePolicy.objects.get(role="public")

        self.assertEqual(hr.writable_types, ["legal"])
        self.assertEqual(public.writable_types, [])

    def test_creates_caller_accounts_and_links_only_self_to_person(self):
        run_seed()

        self.assertEqual(CallerRole.objects.count(), 4)

        zoe = CallerRole.objects.get(user__username="zoe_self")
        hr = CallerRole.objects.get(user__username="hr_user")

        self.assertIsNotNone(zoe.person)
        self.assertIsNone(hr.person)

    def test_seeded_credentials_can_authenticate(self):
        run_seed()

        response = self.client.post(
            "/api/token/",
            {"username": "hr_user", "password": "testpass123"},
        )

        self.assertEqual(response.status_code, 200)

    def test_running_twice_creates_no_duplicates(self):
        run_seed()
        run_seed()

        self.assertEqual(Person.objects.count(), 1)
        self.assertEqual(Identity.objects.count(), 6)
        self.assertEqual(RolePolicy.objects.count(), 4)
        self.assertEqual(User.objects.count(), 4)
        