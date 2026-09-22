from django.contrib import admin

from .models import AuditLog, CallerRole, Identity, Person, RolePolicy

admin.site.register(Person)
admin.site.register(Identity)
admin.site.register(CallerRole)
admin.site.register(RolePolicy)
admin.site.register(AuditLog)
