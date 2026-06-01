"""Serializers (I/O only) for projects."""

from __future__ import annotations

from rest_framework import serializers

from core.utils import absolute_media_url

from .models import Comment, Project, ProjectMembership


class ProjectSerializer(serializers.ModelSerializer):
    """Read/write representation of a project. Owner is assigned server-side."""

    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    thumbnail = serializers.SerializerMethodField()
    thumbnail_upload = serializers.ImageField(
        write_only=True, required=False, source="thumbnail"
    )

    class Meta:
        model = Project
        fields = [
            "id", "name", "description", "status",
            "thumbnail", "thumbnail_upload",
            "owner_email", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "owner_email", "created_at", "updated_at"]

    def get_thumbnail(self, obj) -> str | None:
        return absolute_media_url(obj.thumbnail, self.context.get("request"))


class DashboardSerializer(serializers.Serializer):
    """Shape of the dashboard summary response."""

    total = serializers.IntegerField()
    by_status = serializers.DictField(child=serializers.IntegerField())
    recent = ProjectSerializer(many=True)


class SyncSerializer(serializers.Serializer):
    """Shape of the incremental sync response (CU16)."""

    server_time = serializers.DateTimeField()
    count = serializers.IntegerField()
    changed = ProjectSerializer(many=True)


# --- Collaboration (CU14) ---------------------------------------------------
class ProjectMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = ProjectMembership
        fields = ["id", "project", "user_email", "role", "created_at"]
        read_only_fields = fields


class AddMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=["editor", "viewer"])


class CommentSerializer(serializers.ModelSerializer):
    author_email = serializers.EmailField(source="author.email", read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "project", "author_email", "body", "parent", "created_at"]
        read_only_fields = ["id", "author_email", "created_at"]
