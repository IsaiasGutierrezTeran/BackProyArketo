from django.contrib import admin

from .models import Model3D


@admin.register(Model3D)
class Model3DAdmin(admin.ModelAdmin):
    list_display = ["id", "project", "element_count", "unit", "is_current", "created_at"]
    list_filter = ["is_current", "unit"]
    search_fields = ["project__name"]
    readonly_fields = ["scene_json", "bounds"]
