from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from identity.models import CallerRole, Identity, Person, RolePolicy

User = get_user_model()


# Seeded record for Persona 1 (Zoe) from the design chapter.
# The legal name is the birth name held by HR and medical systems; the
# chosen name is the one used in every other context.
DEMO_IDENTITIES = {
    "legal": ("Sebastian Taylor", "legal"),
    "chosen": ("Zoe Taylor", "public"),
    "preferred": ("Zoe", "informal"),
    "professional": ("Dr Zoe Taylor", "professional"),
    "religious": ("Zoe Maria", "religious"),
    "username": ("zoe_codes", "online"),
}

ROLE_POLICIES = {
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

DEMO_CALLERS = {
    "zoe_self": ("Zoe self account", "self"),
    "hr_user": ("HR system", "hr"),
    "public_user": ("Public caller", "public"),
    "medical_user": ("Clinical system", "medical"),
}


class Command(BaseCommand):
    help = "Create seeded data for the Polynym identity management API"

    def handle(self, *args, **kwargs):
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

        for role, allowed_types in ROLE_POLICIES.items():
            RolePolicy.objects.update_or_create(
                role=role,
                defaults={"allowed_types": allowed_types},
            )

        for username, (caller_name, role) in DEMO_CALLERS.items():
            user, _ = User.objects.get_or_create(username=username)
            user.set_password("testpass123")
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
