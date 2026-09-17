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

def select_by_language(identities, accepted_languages):
    """
    Given identity records of a single type and an ordered list of
    accepted language codes (highest priority first), return the record
    whose language_code best matches.

    Falls back to the first record when no language matches, so a caller
    that expresses no preference, or an unsupported one, still receives a
    name rather than nothing.
    """
    if not accepted_languages:
        return identities[0] if identities else None

    for language in accepted_languages:
        for identity in identities:
            if identity.language_code == language:
                return identity

    return identities[0] if identities else None

def parse_accepted_languages(header_value):
    """
    Parse an HTTP Accept-Language header into a list of language codes,
    ordered by descending quality (q) value.

    "zh;q=0.9, en;q=0.8, fr" -> ["fr", "zh", "en"]

    A code with no explicit q defaults to q=1.0, so it is preferred over
    any weighted code. Codes are lowercased and the region subtag is kept
    (e.g. "en-gb" stays "en-gb"). An empty or absent header yields [].
    """
    if not header_value:
        return []

    parsed = []

    for part in header_value.split(","):
        piece = part.strip()

        if not piece:
            continue

        if ";" in piece:
            code, _, params = piece.partition(";")
            code = code.strip().lower()
            quality = 1.0

            if params.strip().startswith("q="):
                try:
                    quality = float(params.strip()[2:])
                except ValueError:
                    quality = 1.0
        else:
            code = piece.lower()
            quality = 1.0

        if code:
            parsed.append((quality, code))

    parsed.sort(key=lambda pair: pair[0], reverse=True)

    return [code for _, code in parsed]