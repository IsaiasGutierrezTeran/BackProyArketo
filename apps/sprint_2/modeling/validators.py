"""Validators for 3D model editing and import."""

from __future__ import annotations

from rest_framework import serializers

ALLOWED_3D_FORMATS = {"glb", "gltf"}


def validate_scene(scene: object) -> dict:
    """A scene must be an object with a `walls` list (doors/windows optional)."""
    if not isinstance(scene, dict):
        raise serializers.ValidationError("La escena debe ser un objeto JSON.")
    if not isinstance(scene.get("walls"), list):
        raise serializers.ValidationError("La escena debe incluir una lista 'walls'.")
    return scene


def validate_glb_file(file):
    ext = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else ""
    if ext not in ALLOWED_3D_FORMATS:
        raise serializers.ValidationError(
            f"Formato 3D no permitido '.{ext}'. Use: {', '.join(sorted(ALLOWED_3D_FORMATS))}."
        )
    return file
