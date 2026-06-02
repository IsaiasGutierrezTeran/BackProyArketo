"""Serializers (I/O only) for plans."""

from __future__ import annotations

from rest_framework import serializers

from core.utils import absolute_media_url

from .models import Plan
from .validators import validate_plan_file


class PlanSerializer(serializers.ModelSerializer):
    """Read representation with an absolute, mobile-reachable file URL."""

    file_url = serializers.SerializerMethodField()
    uploaded_by_email = serializers.EmailField(source="uploaded_by.email", read_only=True)

    class Meta:
        model = Plan
        fields = [
            "id", "project", "original_format", "size_bytes", "status",
            "file_url", "uploaded_by_email", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_file_url(self, obj) -> str | None:
        return absolute_media_url(obj.file, self.context.get("request"))


class PlanUploadSerializer(serializers.ModelSerializer):
    """Input for uploading a plan: a target project + the file."""

    file = serializers.FileField(write_only=True, validators=[validate_plan_file])

    class Meta:
        model = Plan
        fields = ["project", "file"]
