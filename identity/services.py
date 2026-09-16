from .models import CallerRole, RolePolicy


def get_caller_role(request):
    """
    Return the caller role for the current request.

    The API reads the role from the JWT payload.
    If this is not available, it falls back to the user's CallerRole record.
    """
    token = getattr(request, "auth", None)

    if token is not None:
        role = None

        if hasattr(token, "get"):
            role = token.get("role")

        if role is None and hasattr(token, "payload"):
            role = token.payload.get("role")

        if role:
            return role

    if request.user and request.user.is_authenticated:
        try:
            return request.user.caller_role.role
        except CallerRole.DoesNotExist:
            return None

    return None


def get_allowed_identity_types(role):
    """
    Return the identity types allowed for a caller role.
    """
    try:
        policy = RolePolicy.objects.get(role=role)
        return policy.allowed_types
    except RolePolicy.DoesNotExist:
        return []

def get_writable_identity_types(role):
    """
    Identity types a caller role may create, update or delete.

    Returns an empty list for unknown roles, so a caller with no policy
    can write nothing.
    """
    if not role:
        return []

    try:
        policy = RolePolicy.objects.get(role=role)
    except RolePolicy.DoesNotExist:
        return []

    return policy.writable_types