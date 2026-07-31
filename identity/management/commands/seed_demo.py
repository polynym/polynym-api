from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from identity.models import CallerRole, Identity, Person, RolePolicy


User = get_user_model()


class Command(BaseCommand):
    help = "Create demo data for the Polynym prototype"

    def handle(self, *args, **kwargs):
        person, _ = Person.objects.get_or_create(
            email="maya@example.com"
        )

        Identity.objects.get_or_create(
            person=person,
            type="legal",
            defaults={
                "value": "Maria Thompson",
                "context_tag": "legal",
                "language_code": "en",
                "script_code": "",
            },
        )

        Identity.objects.get_or_create(
            person=person,
            type="chosen",
            defaults={
                "value": "Maya",
                "context_tag": "public",
                "language_code": "en",
                "script_code": "",
            },
        )

        Identity.objects.get_or_create(
            person=person,
            type="username",
            defaults={
                "value": "maya_codes",
                "context_tag": "online",
                "language_code": "en",
                "script_code": "",
            },
        )

        RolePolicy.objects.update_or_create(
            role="self",
            defaults={
                "allowed_types": [
                    "legal",
                    "chosen",
                    "preferred",
                    "religious",
                    "professional",
                    "username",
                ]
            },
        )

        RolePolicy.objects.update_or_create(
            role="hr",
            defaults={"allowed_types": ["legal"]},
        )

        RolePolicy.objects.update_or_create(
            role="public",
            defaults={"allowed_types": ["chosen", "preferred"]},
        )

        self_user, _ = User.objects.get_or_create(username="maya_self")
        self_user.set_password("testpass123")
        self_user.save()

        CallerRole.objects.update_or_create(
            user=self_user,
            defaults={
                "person": person,
                "caller_name": "Maya self account",
                "role": "self",
            },
        )

        hr_user, _ = User.objects.get_or_create(username="hr_user")
        hr_user.set_password("testpass123")
        hr_user.save()

        CallerRole.objects.update_or_create(
            user=hr_user,
            defaults={
                "person": None,
                "caller_name": "HR system",
                "role": "hr",
            },
        )

        public_user, _ = User.objects.get_or_create(username="public_user")
        public_user.set_password("testpass123")
        public_user.save()

        CallerRole.objects.update_or_create(
            user=public_user,
            defaults={
                "person": None,
                "caller_name": "Public caller",
                "role": "public",
            },
        )

        self.stdout.write(
            self.style.SUCCESS("Demo data created successfully.")
        )