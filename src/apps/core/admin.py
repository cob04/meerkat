from django.contrib import admin

from apps.core.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "user", "action", "model_name", "record_id"]
    list_filter = ["action", "model_name", "timestamp"]
    search_fields = ["description", "model_name"]
    readonly_fields = [
        "timestamp",
        "user",
        "action",
        "model_name",
        "record_id",
        "description",
        "metadata",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
