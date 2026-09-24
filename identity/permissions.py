from rest_framework.permissions import BasePermission

from .models import RolePolicy
from .services import get_caller_role


class HasCallerRole(BasePermission):
    """Allow access only if the caller has a configured role policy."""

    message = "Authenticated user does not have an authorised caller role."

    def has_permission(self, request, _view):
        """Check that the caller's role has an associated policy."""
        role = get_caller_role(request)

        return bool(role and RolePolicy.objects.filter(role=role).exists())
