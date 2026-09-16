from django.conf import settings
from django.db import models


class Person(models.Model):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class Identity(models.Model):
    LEGAL = "legal"
    CHOSEN = "chosen"
    PREFERRED = "preferred"
    PROFESSIONAL = "professional"
    RELIGIOUS = "religious"
    USERNAME = "username"

    IDENTITY_TYPE_CHOICES = [
        (LEGAL, "Legal"),
        (CHOSEN, "Chosen"),
        (PREFERRED, "Preferred"),
        (PROFESSIONAL, "Professional"),
        (RELIGIOUS, "Religious"),
        (USERNAME, "Username"),
    ]

    person = models.ForeignKey(
        Person,
        related_name="identities",
        on_delete=models.CASCADE,
    )
    type = models.CharField(max_length=30, choices=IDENTITY_TYPE_CHOICES)
    value = models.CharField(max_length=255)
    context_tag = models.CharField(max_length=100, blank=True)
    language_code = models.CharField(max_length=10, blank=True, default="")
    script_code = models.CharField(max_length=10, blank=True, default="")

    def __str__(self):
        return f"{self.person.email} - {self.type}: {self.value}"


class CallerRole(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="caller_role",
        on_delete=models.CASCADE,
    )
    person = models.ForeignKey(
        Person,
        related_name="caller_roles",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    caller_name = models.CharField(max_length=100)
    role = models.CharField(max_length=30)

    def __str__(self):
        return f"{self.caller_name} ({self.role})"


class RolePolicy(models.Model):
    role = models.CharField(max_length=30, unique=True)
    allowed_types = models.JSONField(default=list)
    writable_types = models.JSONField(default=list)

    def __str__(self):
        return f"{self.role}: read={self.allowed_types} write={self.writable_types}"


class AuditLog(models.Model):
    person = models.ForeignKey(
        Person,
        related_name="audit_logs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    caller_role = models.CharField(max_length=30)
    action = models.CharField(max_length=20)
    fields_returned = models.JSONField(default=list)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} by {self.caller_role} at {self.timestamp}"
