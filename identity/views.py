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
    """
    Frontend web interface page.
    """
    return render(request, "identity/demo.html")


class PersonIdentityDetailView(APIView):
    """
    Protected indetity endpoint:

    GET /api/persons/<id>/identity/

    Returns only the identity records allowed for the caller role.
    """

    permission_classes = (IsAuthenticated, HasCallerRole)

    def get(self, request, person_id):
        person = get_object_or_404(Person, id=person_id)
        role = get_caller_role(request)

        # Self-users may only access their own person record.
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
    """
    GDPR Article 17 erasure:

    DELETE /api/persons/<id>/

    Removes the person record and all associated identity records. Only
    the data subject may erase their own record.
    """

    permission_classes = (IsAuthenticated, HasCallerRole)

    def delete(self, request, person_id):
        person = get_object_or_404(Person, id=person_id)
        role = get_caller_role(request)

        if role != "self":
            raise PermissionDenied(
                "Only the data subject may request erasure of their record."
            )

        caller_person = getattr(request.user.caller_role, "person", None)

        if caller_person is None or caller_person.id != person.id:
            raise PermissionDenied(
                "Self role can only erase its own person record."
            )

        # Record what is being erased before the records are removed. The
        # audit entry deliberately survives erasure: Article 17 requires
        # the personal data to be deleted, while Article 5(2) requires the
        # controller to remain able to show that it was.
        erased_types = sorted(
            person.identities.values_list("type", flat=True)
        )

        AuditLog.objects.create(
            person=person,
            caller_role=role,
            action="DELETE",
            fields_returned=erased_types,
        )

        person.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
    
class PersonIdentityCollectionView(APIView):
    """
    POST /api/persons/<id>/identities/

    Creates an identity record. The caller must be permitted to write
    the requested identity type.
    """

    permission_classes = (IsAuthenticated, HasCallerRole)

    def post(self, request, person_id):
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
                f"Role '{role}' may not write identities of type "
                f"'{requested_type}'."
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
    """
    PUT    /api/identities/<id>/
    DELETE /api/identities/<id>/

    Updates or removes a single identity record.
    """

    permission_classes = (IsAuthenticated, HasCallerRole)

    def _check_write_access(self, request, identity, role):
        if role == "self":
            caller_person = getattr(request.user.caller_role, "person", None)

            if caller_person is None or caller_person.id != identity.person_id:
                raise PermissionDenied(
                    "Self role can only write to its own person record."
                )

        writable = get_writable_identity_types(role)

        # The caller must be permitted to write the type the record
        # currently holds, otherwise a caller could modify a record it
        # has no authority over.
        if identity.type not in writable:
            raise PermissionDenied(
                f"Role '{role}' may not modify identities of type "
                f"'{identity.type}'."
            )

        return writable

    def put(self, request, identity_id):
        identity = get_object_or_404(Identity, id=identity_id)
        role = get_caller_role(request)

        writable = self._check_write_access(request, identity, role)

        serializer = IdentityWriteSerializer(identity, data=request.data)
        serializer.is_valid(raise_exception=True)

        # The target type must also be writable, or a caller could
        # relabel a record into a type it has no permission for.
        target_type = serializer.validated_data["type"]

        if target_type not in writable:
            raise PermissionDenied(
                f"Role '{role}' may not write identities of type "
                f"'{target_type}'."
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