"""Turn a normalized scene dict into a binary glTF (.glb) with trimesh.

Coordinate mapping: the plan's ground plane (x, y) -> world (X, Z); the vertical
axis is Y (up), which is glTF's convention. Walls are extruded as boxes; doors
and windows are added as thin colored markers (no boolean carving, so no external
geometry engine is required).
"""

from __future__ import annotations

import math

import trimesh

WALL_COLOR = [180, 180, 185, 255]
DOOR_COLOR = [150, 90, 40, 255]
WINDOW_COLOR = [90, 160, 220, 200]


def _box(extents, color):
    mesh = trimesh.creation.box(extents=extents)
    mesh.visual.face_colors = color
    return mesh


def _add_opening(scene, opening, color, *, sill: float, default_height: float):
    pos = opening.get("position") or {}
    x = float(pos.get("x", 0.0))
    z = float(pos.get("y", 0.0))
    width = float(opening.get("width") or 0.9)
    height = float(opening.get("height") or default_height)
    mesh = _box([max(width, 0.05), max(height, 0.05), 0.06], color)
    mesh.apply_transform(
        trimesh.transformations.translation_matrix([x, sill + height / 2.0, z])
    )
    scene.add_geometry(mesh, geom_name=str(opening.get("id") or "opening"))


def build_glb_bytes(scene_json: dict) -> bytes:
    """Build a .glb (bytes) from the scene. Always returns a valid glTF."""
    scene = trimesh.Scene()

    for wall in scene_json.get("walls") or []:
        start, end = wall.get("start") or {}, wall.get("end") or {}
        sx, sy = float(start.get("x", 0.0)), float(start.get("y", 0.0))
        ex, ey = float(end.get("x", 0.0)), float(end.get("y", 0.0))
        dx, dy = ex - sx, ey - sy
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            continue
        thickness = float(wall.get("thickness") or 0.15)
        height = float(wall.get("height") or 2.7)
        mesh = _box([length, height, thickness], WALL_COLOR)
        # Rotate about Y so the box's length axis aligns with the wall direction.
        mesh.apply_transform(
            trimesh.transformations.rotation_matrix(-math.atan2(dy, dx), [0, 1, 0])
        )
        mesh.apply_transform(
            trimesh.transformations.translation_matrix(
                [(sx + ex) / 2.0, height / 2.0, (sy + ey) / 2.0]
            )
        )
        scene.add_geometry(mesh, geom_name=str(wall.get("id") or "wall"))

    for door in scene_json.get("doors") or []:
        _add_opening(scene, door, DOOR_COLOR, sill=0.0, default_height=2.1)
    for window in scene_json.get("windows") or []:
        _add_opening(
            scene, window, WINDOW_COLOR,
            sill=float(window.get("sill_height") or 0.9), default_height=1.1,
        )

    # Guarantee non-empty geometry so the export is always a valid glb.
    if not scene.geometry:
        scene.add_geometry(_box([0.01, 0.01, 0.01], WALL_COLOR))

    return scene.export(file_type="glb")
