from django.shortcuts import render
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditLog, Person
from .permissions import HasCallerRole
from .serializers import PersonFilteredSerializer
from .services import get_caller_role


def demo_page(request):
    """
    Simple frontend demonstration page.
    """
    return render(request, "identity/demo.html")


class PersonIdentityDetailView(APIView):
    """
    Prototype endpoint:

    GET /api/persons/<id>/identity/

    Returns only the identity records allowed for the caller role.
    """

    permission_classes = [IsAuthenticated, HasCallerRole]

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
