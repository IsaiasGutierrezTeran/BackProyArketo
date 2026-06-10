"""Serializers (I/O) para HU-18."""

from __future__ import annotations

from rest_framework import serializers

from .models import Boceto2D


class Boceto2DSerializer(serializers.ModelSerializer):
    class Meta:
        model = Boceto2D
        fields = [
            "id", "proyecto", "prompt", "imagen_url",
            "proveedor_ia", "estado", "created_at",
        ]
        read_only_fields = fields


class GenerateSketchSerializer(serializers.Serializer):
    prompt = serializers.CharField()
    project = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    provider = serializers.ChoiceField(
        choices=["mock", "gemini"], required=False, allow_null=True
    )
