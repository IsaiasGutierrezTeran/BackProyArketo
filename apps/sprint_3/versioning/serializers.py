"""Serializers (I/O only) for versioning."""

from __future__ import annotations

from rest_framework import serializers

from .models import ProjectVersion


class ProjectVersionSerializer(serializers.ModelSerializer):
    author_email = serializers.EmailField(source="author.email", read_only=True)

    class Meta:
        model = ProjectVersion
        fields = [
            "id", "project", "version_number", "message",
            "author_email", "snapshot", "created_at",
        ]
        read_only_fields = fields


class CommitSerializer(serializers.Serializer):
    project = serializers.IntegerField(min_value=1)
    message = serializers.CharField(allow_blank=True, required=False)
