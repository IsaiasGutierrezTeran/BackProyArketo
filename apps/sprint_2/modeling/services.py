"""Business logic for 3D models: build/regenerate GLB, import, set current."""

from __future__ import annotations

import io

import trimesh
from django.core.files.base import ContentFile

from projects.services import mark_project_active

from .glb import build_glb_bytes
from .models import Model3D


def _element_count(scene_json: dict) -> int:
    return sum(
        len(scene_json.get(k) or []) for k in ("walls", "doors", "windows")
    )


def _scene_span(scene_json: dict) -> float:
    """Largest XY extent of the geometry (meters or normalized units)."""
    xs: list[float] = []
    ys: list[float] = []
    for w in scene_json.get("walls") or []:
        for pt in (w.get("start") or {}, w.get("end") or {}):
            if isinstance(pt.get("x"), (int, float)):
                xs.append(pt["x"]); ys.append(pt.get("y", 0) or 0)
    for coll in ("doors", "windows"):
        for d in scene_json.get(coll) or []:
            p = d.get("position") or {}
            if isinstance(p.get("x"), (int, float)):
                xs.append(p["x"]); ys.append(p.get("y", 0) or 0)
    if not xs:
        return 0.0
    return max(max(xs) - min(xs), max(ys) - min(ys))


def _ensure_metric_scale(scene_json: dict, *, trigger_below: float = 5.5,
                         target_longest: float = 12.0) -> dict:
    """Rescale a normalized/tiny scene so its longest side ~= ``target_longest`` m.

    Detector output without ``pixels_per_meter`` comes back in 0..1 units, which
    the 2D renderer would draw as ~0.5 m and the 3D builder would rescale on its
    own — leaving 2D and 3D at different scales. Doing it here, once, keeps both
    consistent. No-op for scenes already in meters (span >= trigger). Wall
    thickness is left untouched (the detector emits it already in meters).
    """
    span = _scene_span(scene_json)
    if span <= 0 or span >= trigger_below:
        return scene_json
    f = target_longest / span
    for w in scene_json.get("walls") or []:
        for key in ("start", "end"):
            p = w.get(key) or {}
            if isinstance(p.get("x"), (int, float)):
                p["x"] *= f
            if isinstance(p.get("y"), (int, float)):
                p["y"] *= f
    for coll in ("doors", "windows"):
        for d in scene_json.get(coll) or []:
            p = d.get("position") or {}
            if isinstance(p.get("x"), (int, float)):
                p["x"] *= f
            if isinstance(p.get("y"), (int, float)):
                p["y"] *= f
            if isinstance(d.get("width"), (int, float)):
                d["width"] *= f
    b = scene_json.get("bounds")
    if isinstance(b, dict):
        for k in ("min_x", "min_y", "max_x", "max_y"):
            if isinstance(b.get(k), (int, float)):
                b[k] *= f
    img = scene_json.setdefault("image", {})
    img["unit"] = "meters"
    scene_json.setdefault("meta", {})["rescaled_from"] = round(span, 4)
    return scene_json


def _set_only_current(project, model: Model3D) -> None:
    Model3D.objects.filter(project=project, is_current=True).exclude(pk=model.pk).update(
        is_current=False
    )


def create_model_from_scene(*, project, scene_json: dict, source_plan=None) -> Model3D:
    """Build a GLB from a scene and store it as the project's current model (CU5)."""
    scene_json = _ensure_metric_scale(scene_json)
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
    mark_project_active(project)
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
    mark_project_active(project)
    return model
