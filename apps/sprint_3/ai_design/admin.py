from django.contrib import admin

from .models import DesignRequest


@admin.register(DesignRequest)
class DesignRequestAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "mode", "status", "provider", "created_at"]
    list_filter = ["mode", "status", "provider"]
    readonly_fields = ["result"]
