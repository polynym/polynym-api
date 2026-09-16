from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import CallerRole, Identity, Person
from .services import get_allowed_identity_types, get_caller_role


class PolynymTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Adds the caller role to the JWT payload.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        try:
            token["role"] = user.caller_role.role
        except CallerRole.DoesNotExist:
            token["role"] = ""

        return token


class IdentitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Identity
        fields = (
            "id",
            "type",
            "value",
            "context_tag",
            "language_code",
            "script_code",
        )


class PersonFilteredSerializer(serializers.ModelSerializer):
    identities = serializers.SerializerMethodField()

    class Meta:
        model = Person
        fields = (
            "id",
            "email",
            "identities",
        )

    def to_representation(self, person):
        data = super().to_representation(person)

        request = self.context["request"]
        role = get_caller_role(request)

        # Only the self role should see the email address.
        if role != "self":
            data.pop("email", None)

        return data

    def get_identities(self, person):
        request = self.context["request"]
        role = get_caller_role(request)
        allowed_types = get_allowed_identity_types(role)

        identities = person.identities.filter(type__in=allowed_types)
        return IdentitySerializer(identities, many=True).data

class IdentityWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Identity
        fields = (
            "id",
            "type",
            "value",
            "context_tag",
            "language_code",
            "script_code",
        )
        read_only_fields = ("id")