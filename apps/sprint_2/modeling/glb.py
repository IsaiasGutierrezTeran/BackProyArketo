"""Turn a normalized scene dict into a binary glTF (.glb) with trimesh.

Coordinate mapping: the plan's ground plane (x, y) -> world (X, Z); the vertical
axis is Y (up), which is glTF's convention. Walls are extruded as boxes with real
glTF PBR materials (matte walls, wood floor/doors, translucent glass windows);
doors and windows get a lintel/apron + a simple casing so they read as finished
openings. A floor slab and baseboards make it read as an interior, not raw boxes.

Scale: when the detector has no real-world scale it emits a *normalized* scene
whose footprint spans ~0..1 while wall heights are in meters (~2.7). We scale the
ground plane up so the longest footprint side is a realistic building size; heights
and thicknesses are already in meters and are left untouched.
"""

from __future__ import annotations

import math

import trimesh
from trimesh.visual import TextureVisuals
from trimesh.visual.material import PBRMaterial


def _pbr(name, base_color, *, roughness, metallic=0.0, alpha_mode="OPAQUE",
         double_sided=True):
    """Build a glTF 2.0 PBR material. ``base_color`` is RGBA in 0..1.

    ``alpha_mode='BLEND'`` plus alpha < 1 renders translucent in model-viewer.
    Works without UVs (flat-shaded boxes).
    """
    return PBRMaterial(
        name=name,
        baseColorFactor=list(base_color),
        roughnessFactor=float(roughness),
        metallicFactor=float(metallic),
        alphaMode=alpha_mode,
        doubleSided=double_sided,
    )


WALL_MATERIAL = _pbr("wall", [0.93, 0.92, 0.88, 1.0], roughness=0.9)
FLOOR_MATERIAL = _pbr("floor", [0.62, 0.45, 0.28, 1.0], roughness=0.6)
DOOR_MATERIAL = _pbr("door", [0.40, 0.26, 0.15, 1.0], roughness=0.85)
WINDOW_MATERIAL = _pbr("glass", [0.55, 0.72, 0.85, 0.35], roughness=0.1, alpha_mode="BLEND")
BASEBOARD_MATERIAL = _pbr("baseboard", [0.47, 0.47, 0.50, 1.0], roughness=0.8)
FRAME_MATERIAL = _pbr("frame", [0.55, 0.37, 0.22, 1.0], roughness=0.7)

_OPENING_DEPTH = 0.12  # glass / door panel
_FRAME_DEPTH = 0.20    # lintel / apron (matches wall depth so it reads continuous)

# --- Architectural trim (cheap detail, all axis/extruded boxes) ---
_BASEBOARD_H = 0.10        # baseboard height (m)
_BASEBOARD_EXTRA = 0.04    # how much thicker than the wall (sticks out a bit)
_CASING_W = 0.06           # width/height of the door/window frame profile (m)
_CASING_DEPTH = 0.22       # a touch deeper than the wall so the casing is visible
_ENABLE_WALL_COPING = False
_COPING_H = 0.05
_COPING_EXTRA = 0.03

# A footprint whose longest side is below this is treated as normalized (0..1)
# and scaled up so the longest side becomes TARGET_FOOTPRINT_M meters.
_NORMALIZED_MAX = 5.0
TARGET_FOOTPRINT_M = 14.0


def _wall_points(scene_json: dict):
    """Yield (x, y) of every wall endpoint (plan space, unscaled)."""
    for wall in scene_json.get("walls") or []:
        for pt in (wall.get("start") or {}, wall.get("end") or {}):
            yield float(pt.get("x", 0.0)), float(pt.get("y", 0.0))


def _ground_scale(scene_json: dict) -> float:
    """Factor to bring a normalized footprint to a realistic size (1.0 if already meters)."""
    pts = list(_wall_points(scene_json))
    if not pts:
        return 1.0
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    longest = max(max(xs) - min(xs), max(ys) - min(ys))
    if longest <= 1e-6 or longest > _NORMALIZED_MAX:
        return 1.0
    return TARGET_FOOTPRINT_M / longest


def _box(extents, material):
    """A box mesh with a glTF PBR material applied (no UVs needed)."""
    mesh = trimesh.creation.box(extents=extents)
    mesh.visual = TextureVisuals(material=material)
    return mesh


def _add_floor(scene, scene_json: dict, s: float) -> None:
    """A thin slab covering the (scaled) footprint, so it reads as a house."""
    pts = list(_wall_points(scene_json))
    if not pts:
        return
    xs = [p[0] * s for p in pts]
    ys = [p[1] * s for p in pts]
    w, d = max(xs) - min(xs), max(ys) - min(ys)
    if w <= 0 or d <= 0:
        return
    floor = _box([w + 0.4, 0.06, d + 0.4], FLOOR_MATERIAL)
    floor.apply_transform(
        trimesh.transformations.translation_matrix(
            [(min(xs) + max(xs)) / 2.0, -0.03, (min(ys) + max(ys)) / 2.0]
        )
    )
    scene.add_geometry(floor, geom_name="floor")


def _add_baseboard(scene, sx, sy, ex, ey, thickness, name="baseboard"):
    """A thin skirting box at the foot of a wall (same placement as the wall)."""
    dx, dy = ex - sx, ey - sy
    length = math.hypot(dx, dy)
    if length <= 1e-6:
        return
    bb = _box([length + thickness, _BASEBOARD_H, thickness + _BASEBOARD_EXTRA],
              BASEBOARD_MATERIAL)
    bb.apply_transform(
        trimesh.transformations.rotation_matrix(-math.atan2(dy, dx), [0, 1, 0])
    )
    bb.apply_transform(
        trimesh.transformations.translation_matrix(
            [(sx + ex) / 2.0, _BASEBOARD_H / 2.0, (sy + ey) / 2.0]
        )
    )
    scene.add_geometry(bb, geom_name=name)


def _seg_dist2(px, py, ax, ay, bx, by) -> float:
    """Squared distance from point (px,py) to segment a-b (plan space)."""
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 <= 1e-12:
        return (px - ax) ** 2 + (py - ay) ** 2
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    cx, cy = ax + t * dx, ay + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2


def _host_wall(scene_json: dict, px: float, py: float):
    """(rotation, thickness) of the wall nearest the opening (plan coords).

    The opening's panel and casing must align with their host wall; otherwise
    they stay axis-aligned and look like they stick out of vertical/angled walls.
    """
    best_d = float("inf")
    rot, thickness = 0.0, 0.2
    for wall in scene_json.get("walls") or []:
        start, end = wall.get("start") or {}, wall.get("end") or {}
        ax, ay = float(start.get("x", 0.0)), float(start.get("y", 0.0))
        bx, by = float(end.get("x", 0.0)), float(end.get("y", 0.0))
        d = _seg_dist2(px, py, ax, ay, bx, by)
        if d < best_d:
            best_d = d
            rot = -math.atan2(by - ay, bx - ax)
            thickness = max(float(wall.get("thickness") or 0.15), 0.18)
    return rot, thickness


def _place_in_opening(scene, extents, material, *, x, z, ly, rot, lx=0.0, lz=0.0, name):
    """Place an opening sub-box: local offset (lx along the wall, lz across it) and
    vertical center ly, rotated to the host-wall angle, then moved to world (x, z)."""
    mesh = _box(extents, material)
    t1 = trimesh.transformations.translation_matrix([lx, ly, lz])
    r = trimesh.transformations.rotation_matrix(rot, [0, 1, 0])
    t2 = trimesh.transformations.translation_matrix([x, 0.0, z])
    mesh.apply_transform(t2 @ r @ t1)
    scene.add_geometry(mesh, geom_name=name)


def _add_opening_frame(scene, x, z, width, sill, height, *, rot, casing_depth, name="frame"):
    """A simple casing around a door/window: 2 jambs + head (+ sill for windows).

    Aligned to the host wall (``rot``) and flush within its thickness (``casing_depth``).
    """
    if width <= 0.01 or height <= 0.01:
        return
    top = sill + height
    outer_w = width + 2.0 * _CASING_W
    _place_in_opening(scene, [outer_w, _CASING_W, casing_depth], FRAME_MATERIAL,
                      x=x, z=z, ly=top + _CASING_W / 2.0, rot=rot, name=name + "_head")
    jamb_h = height + _CASING_W
    for sign in (-1.0, 1.0):
        _place_in_opening(scene, [_CASING_W, jamb_h, casing_depth], FRAME_MATERIAL,
                          x=x, z=z, ly=sill + jamb_h / 2.0, rot=rot,
                          lx=sign * (width / 2.0 + _CASING_W / 2.0), name=name + "_jamb")
    if sill > 0.05:
        _place_in_opening(scene, [outer_w, _CASING_W, casing_depth], FRAME_MATERIAL,
                          x=x, z=z, ly=sill - _CASING_W / 2.0, rot=rot, name=name + "_sill")


def _add_wall_coping(scene, sx, sy, ex, ey, thickness, height, name="coping"):
    """Optional thin wider cap on top of a wall (disabled by default)."""
    dx, dy = ex - sx, ey - sy
    length = math.hypot(dx, dy)
    if length <= 1e-6:
        return
    cap = _box([length + thickness + _COPING_EXTRA, _COPING_H,
                thickness + _COPING_EXTRA], WALL_MATERIAL)
    cap.apply_transform(
        trimesh.transformations.rotation_matrix(-math.atan2(dy, dx), [0, 1, 0])
    )
    cap.apply_transform(
        trimesh.transformations.translation_matrix(
            [(sx + ex) / 2.0, height + _COPING_H / 2.0, (sy + ey) / 2.0]
        )
    )
    scene.add_geometry(cap, geom_name=name)


def _add_opening(scene, opening, material, *, sill: float, default_height: float,
                 s: float, wall_h: float, scene_json: dict):
    """Place an opening (door/window) + the wall that frames it + a casing.

    The panel (glass/door) sits in the opening; a *lintel* fills the wall up to the
    ceiling (so windows aren't "empty above"); an *apron* fills below the sill for
    windows; and a simple frame (head + jambs + sill) makes it read as finished.
    Everything is rotated to the host wall and kept WITHIN the wall thickness so the
    opening reads flush with the wall, not sticking out.
    """
    pos = opening.get("position") or {}
    px, py = float(pos.get("x", 0.0)), float(pos.get("y", 0.0))
    x, z = px * s, py * s
    width = max(float(opening.get("width") or 0.9) * s, 0.45)
    height = max(float(opening.get("height") or default_height), 0.3)
    top = sill + height

    rot, thickness = _host_wall(scene_json, px, py)
    # Depths live inside the wall thickness -> the opening sits flush, not proud.
    panel_depth = min(_OPENING_DEPTH, max(thickness - 0.04, 0.04))
    frame_depth = thickness  # lintel / apron fill the wall exactly

    _place_in_opening(scene, [width, height, panel_depth], material,
                      x=x, z=z, ly=sill + height / 2.0, rot=rot,
                      name=str(opening.get("id") or "opening"))
    _add_opening_frame(scene, x, z, width, sill, height, rot=rot, casing_depth=thickness,
                       name=str(opening.get("id") or "opening") + "_frame")

    frame_w = width + 0.12
    if wall_h - top > 0.05:  # lintel: wall above the opening up to the ceiling
        lh = wall_h - top
        _place_in_opening(scene, [frame_w, lh, frame_depth], WALL_MATERIAL,
                          x=x, z=z, ly=top + lh / 2.0, rot=rot, name="lintel")
    if sill > 0.05:  # apron: wall below the sill (windows)
        _place_in_opening(scene, [frame_w, sill, frame_depth], WALL_MATERIAL,
                          x=x, z=z, ly=sill / 2.0, rot=rot, name="apron")


def build_glb_bytes(scene_json: dict) -> bytes:
    """Build a .glb (bytes) from the scene. Always returns a valid glTF."""
    scene = trimesh.Scene()
    s = _ground_scale(scene_json)
    wall_h = float((scene_json.get("scale") or {}).get("wall_height") or 2.7)

    _add_floor(scene, scene_json, s)

    for wall in scene_json.get("walls") or []:
        start, end = wall.get("start") or {}, wall.get("end") or {}
        sx, sy = float(start.get("x", 0.0)) * s, float(start.get("y", 0.0)) * s
        ex, ey = float(end.get("x", 0.0)) * s, float(end.get("y", 0.0)) * s
        dx, dy = ex - sx, ey - sy
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            continue
        thickness = max(float(wall.get("thickness") or 0.15), 0.18)
        height = float(wall.get("height") or 2.7)
        # Extend half a thickness at each end so walls overlap at corners.
        mesh = _box([length + thickness, height, thickness], WALL_MATERIAL)
        mesh.apply_transform(
            trimesh.transformations.rotation_matrix(-math.atan2(dy, dx), [0, 1, 0])
        )
        mesh.apply_transform(
            trimesh.transformations.translation_matrix(
                [(sx + ex) / 2.0, height / 2.0, (sy + ey) / 2.0]
            )
        )
        scene.add_geometry(mesh, geom_name=str(wall.get("id") or "wall"))
        _add_baseboard(scene, sx, sy, ex, ey, thickness,
                       name=str(wall.get("id") or "wall") + "_base")
        if _ENABLE_WALL_COPING:
            _add_wall_coping(scene, sx, sy, ex, ey, thickness, height,
                             name=str(wall.get("id") or "wall") + "_coping")

    for door in scene_json.get("doors") or []:
        _add_opening(scene, door, DOOR_MATERIAL, sill=0.0, default_height=2.1,
                     s=s, wall_h=wall_h, scene_json=scene_json)
    for window in scene_json.get("windows") or []:
        _add_opening(
            scene, window, WINDOW_MATERIAL,
            sill=float(window.get("sill_height") or 0.9), default_height=1.1,
            s=s, wall_h=wall_h, scene_json=scene_json,
        )

    # Guarantee non-empty geometry so the export is always a valid glb.
    if not scene.geometry:
        scene.add_geometry(_box([0.01, 0.01, 0.01], WALL_MATERIAL))

    return scene.export(file_type="glb")
