from rest_framework.permissions import BasePermission

from .services import get_caller_role


class HasCallerRole(BasePermission):
    """
    Allows access only if the authenticated caller has a recognised role.
    """

    message = "Authenticated user does not have a caller role."

    def has_permission(self, request, view):
        return get_caller_role(request) is not None
