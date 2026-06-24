"""Serializers (I/O only) for 3D models."""

from __future__ import annotations

from rest_framework import serializers

from core.utils import absolute_media_url

from .models import Model3D
from .validators import validate_glb_file, validate_scene


class Model3DSerializer(serializers.ModelSerializer):
    """Read representation with an absolute, mobile-reachable GLB URL (CU6)."""

    glb_url = serializers.SerializerMethodField()

    class Meta:
        model = Model3D
        fields = [
            "id",
            "project",
            "source_plan",
            "glb_url",
            "scene_json",
            "bounds",
            "element_count",
            "model_name",
            "unit",
            "is_current",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_glb_url(self, obj) -> str | None:
        return absolute_media_url(obj.glb_file, self.context.get("request"))


class SceneEditSerializer(serializers.Serializer):
    """Edited geometry to persist + re-extrude (CU7)."""

    scene = serializers.JSONField(validators=[validate_scene])


class ImportGlbSerializer(serializers.Serializer):
    """Import an external GLB/GLTF into a project (CU8)."""

    project = serializers.IntegerField(min_value=1)
    file = serializers.FileField(validators=[validate_glb_file])
