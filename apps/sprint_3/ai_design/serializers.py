"""Serializers (I/O only) for AI design."""

from __future__ import annotations

from rest_framework import serializers

from core.utils import absolute_media_url
from modeling.serializers import Model3DSerializer

from .models import DesignRequest


class DesignRequestSerializer(serializers.ModelSerializer):
    model = Model3DSerializer(source="model3d", read_only=True)
    audio_url = serializers.SerializerMethodField()

    class Meta:
        model = DesignRequest
        fields = [
            "id", "mode", "project", "prompt_text", "transcript", "provider",
            "status", "result", "model", "audio_url", "error", "created_at",
        ]
        read_only_fields = fields

    def get_audio_url(self, obj) -> str | None:
        return absolute_media_url(obj.audio_file, self.context.get("request"))


class TextDesignSerializer(serializers.Serializer):
    prompt = serializers.CharField()
    project = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    provider = serializers.ChoiceField(choices=["mock", "gemini"], required=False, allow_null=True)


class AudioDesignSerializer(serializers.Serializer):
    audio = serializers.FileField()
    project = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    provider = serializers.ChoiceField(choices=["mock", "gemini"], required=False, allow_null=True)


class AssistantSerializer(serializers.Serializer):
    message = serializers.CharField()
    request = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    project = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    provider = serializers.ChoiceField(choices=["mock", "gemini"], required=False, allow_null=True)
