"""Serializers (I/O only) for detection."""

from __future__ import annotations

from rest_framework import serializers

from modeling.serializers import Model3DSerializer

from .models import DetectionJob


class RunDetectionSerializer(serializers.Serializer):
    """Input to trigger detection over an uploaded plan."""

    plan = serializers.IntegerField(min_value=1)
    detector = serializers.ChoiceField(
        choices=["mock", "maskrcnn", "gemini-vision"],
        required=False,
        allow_null=True,
    )
    pixels_per_meter = serializers.FloatField(
        required=False, allow_null=True, min_value=0.0001
    )
    confidence_threshold = serializers.FloatField(
        required=False, allow_null=True, min_value=0.0, max_value=1.0
    )


class DetectionJobSerializer(serializers.ModelSerializer):
    """Output: the job plus the produced 3D model (if any)."""

    model = Model3DSerializer(source="model3d", read_only=True)

    class Meta:
        model = DetectionJob
        fields = [
            "id",
            "plan",
            "detector",
            "status",
            "processing_ms",
            "error",
            "model",
            "created_at",
        ]
        read_only_fields = fields
