from django.contrib import admin

from .models import Boceto2D


@admin.register(Boceto2D)
class Boceto2DAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "usuario",
        "proyecto",
        "proveedor_ia",
        "estado",
        "created_at",
    ]
    list_filter = ["estado", "proveedor_ia"]
    search_fields = ["prompt"]
