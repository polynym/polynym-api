"""Create the seeded data used to demonstrate how Polynym works.

The demonstration person is Zoe Taylor from Persona 1 in the design
chapter of the report. The seeded records include legal, chosen, preferred,
professional, religious and username identities together with caller roles
and disclosure policies.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from identity.models import CallerRole, Identity, Person, RolePolicy

User = get_user_model()


DEMO_IDENTITIES = {
    "legal": ("Sebastian Taylor", "legal"),
    "chosen": ("Zoe Taylor", "public"),
    "preferred": ("Zoe", "informal"),
    "professional": ("Dr Zoe Taylor", "professional"),
    "religious": ("Zoe Maria", "religious"),
    "username": ("zoe_codes", "online"),
}

ROLE_POLICIES = {
    "self": {
        "read": [
            "legal",
            "chosen",
            "preferred",
            "professional",
            "religious",
            "username",
        ],
        "write": [
            "legal",
            "chosen",
            "preferred",
            "professional",
            "religious",
            "username",
        ],
    },
    "hr": {
        "read": ["legal"],
        "write": ["legal"],
    },
    "public": {
        "read": ["chosen", "preferred"],
        "write": [],
    },
    "medical": {
        "read": ["legal", "chosen"],
        "write": [],
    },
}

DEMO_CALLERS = {
    "zoe_self": ("Zoe self account", "self", "DEMO_SELF_PASSWORD"),
    "hr_user": ("HR system", "hr", "DEMO_HR_PASSWORD"),
    "public_user": ("Public caller", "public", "DEMO_PUBLIC_PASSWORD"),
    "medical_user": ("Clinical system", "medical", "DEMO_MEDICAL_PASSWORD"),
}


class Command(BaseCommand):
    """Create the demonstration data used to show how Polynym works."""

    help = "Create seeded data for the Polynym identity management API"

    def handle(self, *args, **kwargs):
        """Create or update the seeded demonstration data."""
        missing_passwords = [
            environment_variable
            for _, (_, _, environment_variable) in DEMO_CALLERS.items()
            if not os.environ.get(environment_variable)
        ]

        if missing_passwords:
            raise CommandError(
                "Missing required demo password environment variable(s): "
                + ", ".join(missing_passwords)
            )

        passwords = {
            username: os.environ[environment_variable]
            for username, (_, _, environment_variable) in DEMO_CALLERS.items()
        }

        person, _ = Person.objects.get_or_create(email="zoe.taylor@example.com")

        for identity_type, (value, context_tag) in DEMO_IDENTITIES.items():
            Identity.objects.get_or_create(
                person=person,
                type=identity_type,
                defaults={
                    "value": value,
                    "context_tag": context_tag,
                    "language_code": "en",
                    "script_code": "",
                },
            )

        for role, policy in ROLE_POLICIES.items():
            RolePolicy.objects.update_or_create(
                role=role,
                defaults={
                    "allowed_types": policy["read"],
                    "writable_types": policy["write"],
                },
            )

        for username, (caller_name, role, _) in DEMO_CALLERS.items():
            user, _ = User.objects.get_or_create(username=username)
            user.set_password(passwords[username])
            user.save()

            CallerRole.objects.update_or_create(
                user=user,
                defaults={
                    "person": person if role == "self" else None,
                    "caller_name": caller_name,
                    "role": role,
                },
            )

        self.stdout.write(self.style.SUCCESS("Seed data created successfully."))
