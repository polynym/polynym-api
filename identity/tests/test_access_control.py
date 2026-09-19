from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from identity.models import Identity, Person

from .fixtures import PolicyFixtureMixin


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
