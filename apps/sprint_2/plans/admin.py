from django.contrib import admin

from .models import Plan


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["id", "project", "original_format", "status", "size_bytes", "created_at"]
    list_filter = ["status", "original_format"]
    search_fields = ["project__name"]
    autocomplete_fields = ["project", "uploaded_by"]
