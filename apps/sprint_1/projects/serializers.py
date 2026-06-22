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
    """A collaborator row as seen by the project owner (includes invite status)."""

    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = ProjectMembership
        fields = ["id", "project", "user_email", "user_full_name", "role", "status", "created_at"]
        read_only_fields = fields


class InvitationSerializer(serializers.ModelSerializer):
    """A pending invitation as seen by the invited user (their inbox)."""

    project_name = serializers.CharField(source="project.name", read_only=True)
    owner_email = serializers.EmailField(source="project.owner.email", read_only=True)
    invited_by_email = serializers.EmailField(source="invited_by.email", read_only=True, default=None)

    class Meta:
        model = ProjectMembership
        fields = [
            "id", "project", "project_name", "owner_email",
            "invited_by_email", "role", "status", "created_at",
        ]
        read_only_fields = fields


class AssignableUserSerializer(serializers.Serializer):
    """A user the owner can pick from the list to invite."""

    id = serializers.IntegerField()
    email = serializers.EmailField()
    full_name = serializers.CharField(allow_blank=True)
    role = serializers.CharField()


class InviteMemberSerializer(serializers.Serializer):
    """Invite the picked user (by id) with a collaboration role."""

    user = serializers.IntegerField(min_value=1)
    role = serializers.ChoiceField(choices=["editor", "viewer"])


class CommentSerializer(serializers.ModelSerializer):
    author_email = serializers.EmailField(source="author.email", read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "project", "author_email", "body", "parent", "created_at"]
        read_only_fields = ["id", "author_email", "created_at"]
