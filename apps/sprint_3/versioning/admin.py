from django.contrib import admin

from .models import ProjectVersion


@admin.register(ProjectVersion)
class ProjectVersionAdmin(admin.ModelAdmin):
    list_display = ["id", "project", "version_number", "author", "created_at"]
    list_filter = ["project"]
    readonly_fields = ["snapshot"]
