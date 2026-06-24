from django.contrib import admin

from .models import (
    Budget,
    BudgetItem,
    BudgetReview,
    Material,
    MaterialCategory,
)


@admin.register(MaterialCategory)
class MaterialCategoryAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["name"]


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "category",
        "unit",
        "unit_price",
        "block_quality",
        "is_active",
    ]
    list_filter = ["block_quality", "is_active", "category"]
    search_fields = ["name"]


class BudgetItemInline(admin.TabularInline):
    model = BudgetItem
    extra = 0
    readonly_fields = ["unit_price_snapshot", "subtotal"]


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "project",
        "status",
        "total",
        "currency",
        "created_at",
    ]
    list_filter = ["status", "currency"]
    inlines = [BudgetItemInline]


admin.site.register(BudgetReview)
