from django.shortcuts import render
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditLog, Identity, Person
from .permissions import HasCallerRole
from .serializers import IdentityWriteSerializer, PersonFilteredSerializer
from .services import get_caller_role, get_writable_identity_types


def demo_page(request):
    """Render the frontend web interface."""
    person = Person.objects.filter(email="zoe.taylor@example.com").first()

    return render(
        request,
        "identity/demo.html",
        {"demo_person_id": person.id if person else None},
    )


class PersonIdentityDetailView(APIView):
    """Return identity records permitted for the authenticated caller."""

    permission_classes = (IsAuthenticated, HasCallerRole)

    def get(self, request, person_id):
        """Return permitted identities and ensure users with the self role can only access their own record."""
        person = get_object_or_404(Person, id=person_id)
        role = get_caller_role(request)

        if role == "self":
            caller_person = getattr(request.user.caller_role, "person", None)

            if caller_person is None or caller_person.id != person.id:
                raise PermissionDenied(
                    "Self role can only access its own person record."
                )

        serializer = PersonFilteredSerializer(
            person,
            context={"request": request},
        )

        data = serializer.data

        AuditLog.objects.create(
            person=person,
            caller_role=role,
            action="GET",
            fields_returned=[item["type"] for item in data["identities"]],
        )

        return Response(data)


class PersonErasureView(APIView):
    """Handle prototype erasure inspired by GDPR Article 17."""

    permission_classes = (IsAuthenticated, HasCallerRole)

    def delete(self, request, person_id):
        """Delete the user's own record while keeping an audit log that no longer identifies the deleted person."""
        person = get_object_or_404(Person, id=person_id)
        role = get_caller_role(request)

        if role != "self":
            raise PermissionDenied(
                "Only the data subject may request erasure of their record."
            )

        caller_person = getattr(request.user.caller_role, "person", None)

        if caller_person is None or caller_person.id != person.id:
            raise PermissionDenied("Self role can only erase its own person record.")

        erased_types = sorted(person.identities.values_list("type", flat=True))

        AuditLog.objects.create(
            person=person,
            caller_role=role,
            action="DELETE",
            fields_returned=erased_types,
        )

        person.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class PersonIdentityCollectionView(APIView):
    """Create a new identity record only when the caller has write permission for that identity type."""

    permission_classes = (IsAuthenticated, HasCallerRole)

    def post(self, request, person_id):
        """Create an identity record when the caller has write permission for its type."""
        person = get_object_or_404(Person, id=person_id)
        role = get_caller_role(request)

        if role == "self":
            caller_person = getattr(request.user.caller_role, "person", None)

            if caller_person is None or caller_person.id != person.id:
                raise PermissionDenied(
                    "Self role can only write to its own person record."
                )

        serializer = IdentityWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        requested_type = serializer.validated_data["type"]
        writable = get_writable_identity_types(role)

        if requested_type not in writable:
            raise PermissionDenied(
                f"Role '{role}' may not write identities of type '{requested_type}'."
            )

        identity = serializer.save(person=person)

        AuditLog.objects.create(
            person=person,
            caller_role=role,
            action="POST",
            fields_returned=[identity.type],
        )

        return Response(
            IdentityWriteSerializer(identity).data,
            status=status.HTTP_201_CREATED,
        )


class IdentityDetailView(APIView):
    """Update or delete one specific identity record."""

    permission_classes = (IsAuthenticated, HasCallerRole)

    def _check_write_access(self, request, identity, role):
        """Check ownership and write permission for the identity's current type."""
        if role == "self":
            caller_person = getattr(request.user.caller_role, "person", None)

            if caller_person is None or caller_person.id != identity.person_id:
                raise PermissionDenied(
                    "Self role can only write to its own person record."
                )

        writable = get_writable_identity_types(role)

        if identity.type not in writable:
            raise PermissionDenied(
                f"Role '{role}' may not modify identities of type '{identity.type}'."
            )

        return writable

    def put(self, request, identity_id):
        """Update an identity only when the caller has write permission for both the existing type and the new type."""
        identity = get_object_or_404(Identity, id=identity_id)
        role = get_caller_role(request)

        writable = self._check_write_access(request, identity, role)

        serializer = IdentityWriteSerializer(identity, data=request.data)
        serializer.is_valid(raise_exception=True)

        target_type = serializer.validated_data["type"]

        if target_type not in writable:
            raise PermissionDenied(
                f"Role '{role}' may not write identities of type '{target_type}'."
            )

        updated = serializer.save()

        AuditLog.objects.create(
            person=updated.person,
            caller_role=role,
            action="PUT",
            fields_returned=[updated.type],
        )

        return Response(IdentityWriteSerializer(updated).data)

    def delete(self, request, identity_id):
        """Delete an identity only when the caller has write permission for that identity type."""
        identity = get_object_or_404(Identity, id=identity_id)
        role = get_caller_role(request)

        self._check_write_access(request, identity, role)

        person = identity.person
        removed_type = identity.type

        identity.delete()

        AuditLog.objects.create(
            person=person,
            caller_role=role,
            action="DELETE_IDENTITY",
            fields_returned=[removed_type],
        )

        return Response(status=status.HTTP_204_NO_CONTENT)
