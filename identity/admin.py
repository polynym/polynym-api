from django.contrib import admin

from .models import Person, Identity, CallerRole, RolePolicy, AuditLog


admin.site.register(Person)
admin.site.register(Identity)
admin.site.register(CallerRole)
admin.site.register(RolePolicy)
admin.site.register(AuditLog)