from django.contrib import admin

from .models import RiskAnalysis, RiskFinding


class RiskFindingInline(admin.TabularInline):
    model = RiskFinding
    extra = 0


@admin.register(RiskAnalysis)
class RiskAnalysisAdmin(admin.ModelAdmin):
    list_display = ["id", "model3d", "provider", "status", "created_at"]
    list_filter = ["provider", "status"]
    inlines = [RiskFindingInline]
