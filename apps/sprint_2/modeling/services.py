"""Business logic for 3D models: build/regenerate GLB, import, set current."""

from __future__ import annotations

import io

import trimesh
from django.core.files.base import ContentFile

from .glb import build_glb_bytes
from .models import Model3D


def _element_count(scene_json: dict) -> int:
    return sum(
        len(scene_json.get(k) or []) for k in ("walls", "doors", "windows")
    )


def _set_only_current(project, model: Model3D) -> None:
    Model3D.objects.filter(project=project, is_current=True).exclude(pk=model.pk).update(
        is_current=False
    )


def create_model_from_scene(*, project, scene_json: dict, source_plan=None) -> Model3D:
    """Build a GLB from a scene and store it as the project's current model (CU5)."""
    glb = build_glb_bytes(scene_json)
    model = Model3D(
        project=project,
        source_plan=source_plan,
        scene_json=scene_json,
        bounds=scene_json.get("bounds"),
        element_count=_element_count(scene_json),
        model_name=(scene_json.get("meta") or {}).get("model", ""),
        unit=(scene_json.get("image") or {}).get("unit", "meters"),
        is_current=True,
    )
    model.glb_file.save(f"project_{project.id}.glb", ContentFile(glb), save=False)
    model.save()
    _set_only_current(project, model)
    return model


def replace_scene(*, model: Model3D, scene_json: dict) -> Model3D:
    """Apply edited geometry (move/scale/delete) and regenerate the GLB (CU7)."""
    glb = build_glb_bytes(scene_json)
    model.scene_json = scene_json
    model.bounds = scene_json.get("bounds")
    model.element_count = _element_count(scene_json)
    model.glb_file.save(f"project_{model.project_id}.glb", ContentFile(glb), save=False)
    model.save()
    return model


def _inspect_glb(raw: bytes) -> tuple[dict | None, int]:
    """Best-effort: read bounding box + geometry count from an imported GLB (CU8).

    Returns ``(bounds, element_count)``. Never raises: a malformed file just
    yields ``(None, 0)`` so the import still succeeds and the model is stored.
    """
    try:
        loaded = trimesh.load(io.BytesIO(raw), file_type="glb")
    except Exception:
        return None, 0
    try:
        geometry = getattr(loaded, "geometry", None)
        count = len(geometry) if geometry is not None else 1
    except Exception:
        count = 0
    bounds = None
    try:
        box = loaded.bounds
        if box is not None:
            bounds = {
                "min": {"x": float(box[0][0]), "y": float(box[0][1]), "z": float(box[0][2])},
                "max": {"x": float(box[1][0]), "y": float(box[1][1]), "z": float(box[1][2])},
            }
    except Exception:
        bounds = None
    return bounds, count


def import_glb(*, project, glb_file, source_plan=None) -> Model3D:
    """Import an externally-authored GLB/GLTF as the project's current model (CU8).

    The binary is inspected with trimesh to populate ``bounds`` and
    ``element_count`` so the imported model carries the same metadata the viewer
    uses for native models (HU-6/HU-8).
    """
    raw = glb_file.read()
    bounds, count = _inspect_glb(raw)
    model = Model3D(
        project=project,
        source_plan=source_plan,
        scene_json=None,
        bounds=bounds,
        element_count=count,
        model_name="imported",
        is_current=True,
    )
    model.glb_file.save(glb_file.name, ContentFile(raw), save=False)
    model.save()
    _set_only_current(project, model)
    return model
