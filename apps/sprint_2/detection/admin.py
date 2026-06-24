from django.contrib import admin

from .models import DetectionJob


@admin.register(DetectionJob)
class DetectionJobAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "plan",
        "detector",
        "status",
        "processing_ms",
        "created_at",
    ]
    list_filter = ["status", "detector"]
    readonly_fields = ["raw_result", "processing_ms"]
