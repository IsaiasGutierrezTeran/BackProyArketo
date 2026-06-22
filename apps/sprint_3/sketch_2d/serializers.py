"""Serializers (I/O) para HU-18."""

from __future__ import annotations

from rest_framework import serializers

from core.utils import absolute_media_url

from .models import Boceto2D


class Boceto2DSerializer(serializers.ModelSerializer):
    # URL absoluta calculada al leer (en S3, prefirmada y fresca en cada respuesta).
    imagen_url = serializers.SerializerMethodField()

    class Meta:
        model = Boceto2D
        fields = [
            "id", "proyecto", "prompt", "imagen_url",
            "proveedor_ia", "estado", "created_at",
        ]
        read_only_fields = fields

    def get_imagen_url(self, obj) -> str | None:
        return absolute_media_url(obj.imagen, self.context.get("request"))


class GenerateSketchSerializer(serializers.Serializer):
    prompt = serializers.CharField()
    project = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    provider = serializers.ChoiceField(
        choices=["mock", "gemini"], required=False, allow_null=True
    )
