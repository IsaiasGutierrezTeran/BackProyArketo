"""Serializers (I/O only) for risk analysis."""

from __future__ import annotations

from rest_framework import serializers

from .models import RiskAnalysis, RiskFinding


class RiskFindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskFinding
        fields = ["id", "category", "severity", "description", "suggestion"]
        read_only_fields = fields


class RiskAnalysisSerializer(serializers.ModelSerializer):
    findings = RiskFindingSerializer(many=True, read_only=True)

    class Meta:
        model = RiskAnalysis
        fields = [
            "id",
            "model3d",
            "provider",
            "status",
            "summary",
            "findings",
            "created_at",
        ]
        read_only_fields = fields


class AnalyzeSerializer(serializers.Serializer):
    model3d = serializers.IntegerField(min_value=1)
    analyzer = serializers.ChoiceField(
        choices=["mock", "gemini"], required=False, allow_null=True
    )
