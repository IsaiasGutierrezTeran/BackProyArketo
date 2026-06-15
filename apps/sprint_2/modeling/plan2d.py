"""Render a technical, AutoCAD-style 2D architectural floor plan (top / cenital).

Black-and-white technical drawing (no render, no shading, no 3D): white sheet,
black lines, real wall thickness, door swing arcs, technical window symbols, room
labels with areas, dimension lines (cotas) in meters, a north arrow, a scale note
("ESC. 1:100") and an areas table (cuadro de areas).

Input is the shared ``scene_json`` contract (identical on every side):

    {
      "image":   {"unit": "meters", "pixels_per_meter": null},
      "scale":   {"wall_height": 2.7, "default_wall_thickness": 0.12},
      "walls":   [{"id","start":{"x","y"},"end":{"x","y"},"thickness","height","confidence"}],
      "doors":   [{"id","wall_id":null,"position":{"x","y"},"width","height","confidence"}],
      "windows": [{"id","wall_id":null,"position":{"x","y"},"width","height","sill_height","confidence"}],
      "rooms":   [{"name","x","y","w","h","area"}],   # x,y = CENTRE of the room
      "bounds":  {"min_x","min_y","max_x","max_y"},
      "meta":    {"model","version"}
    }

Coordinates are in METERS on the building plan (x, y) with origin (0, 0) at the
BOTTOM-LEFT, so y grows upward in the world. On screen we flip Y so the drawing
reads the conventional way (north up). Exterior walls are thicker (0.20 m) and
interior walls thinner (0.12 m); we honour each wall's own ``thickness``.

Two entry points:

* ``render_png(scene_json) -> bytes`` : top-down technical plan PNG.
* ``render_pdf(scene_json) -> bytes`` : the same plan on landscape A4, titled
  "Arketo - Plano Arquitectonico 2D".

Both are defensive: missing keys, ``None`` values, empty/degenerate geometry and
odd numbers never raise — at worst you get a white sheet stamped "Sin geometria".
Returned bytes always carry a valid magic number
(PNG: ``89 50 4E 47``; PDF: ``%PDF``).
"""

from __future__ import annotations

import io
import math

from PIL import Image, ImageDraw, ImageFont

# --- Canvas / layout (px) --------------------------------------------------
_CANVAS = 1654          # PNG drawing area (A-ish landscape proportions)
_CANVAS_H = 1169
_MARGIN = 150           # white border + room for the drawing frame
_MIN_THICKNESS_PX = 4   # walls are never thinner than this on screen
_MAX_THICKNESS_PX = 40  # ...nor absurdly thick when the scene is tiny

# --- Black & white technical palette ---------------------------------------
_BG = (255, 255, 255)
_INK = (0, 0, 0)              # everything is black: technical line drawing
_HATCH = (0, 0, 0)
_DIM = (0, 0, 0)             # dimension lines
_GREY = (110, 110, 110)      # secondary text only (never on geometry)

# --- PDF page (landscape A4 @ 150 DPI) -------------------------------------
_PDF_DPI = 150
_A4_LANDSCAPE_PX = (1754, 1240)   # 297 x 210 mm @ 150 DPI


# --------------------------------------------------------------------------- #
# Coercion helpers
# --------------------------------------------------------------------------- #
def _num(value, default=0.0):
    """Coerce *value* to a finite float, tolerating None / strings / junk."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return float(default)
    if math.isnan(f) or math.isinf(f):
        return float(default)
    return f


def _point(obj):
    """Read an {x, y} mapping into a (x, y) float tuple (defensively)."""
    obj = obj or {}
    return _num(obj.get("x")), _num(obj.get("y"))


def _walls(scene_json):
    return (scene_json or {}).get("walls") or []


def _doors(scene_json):
    return (scene_json or {}).get("doors") or []


def _windows(scene_json):
    return (scene_json or {}).get("windows") or []


def _rooms(scene_json):
    return (scene_json or {}).get("rooms") or []


# --------------------------------------------------------------------------- #
# Bounds
# --------------------------------------------------------------------------- #
def _collect_points(scene_json):
    """Every (x, y) that contributes to the plan extents (in world meters)."""
    pts = []
    for wall in _walls(scene_json):
        pts.append(_point(wall.get("start")))
        pts.append(_point(wall.get("end")))
    for opening in list(_doors(scene_json)) + list(_windows(scene_json)):
        pts.append(_point(opening.get("position")))
    for room in _rooms(scene_json):
        cx, cy = _num(room.get("x")), _num(room.get("y"))
        w, h = _num(room.get("w")), _num(room.get("h"))
        pts.append((cx - w / 2.0, cy - h / 2.0))
        pts.append((cx + w / 2.0, cy + h / 2.0))
    return pts


def _bounds(scene_json):
    """(min_x, min_y, max_x, max_y) in world meters, or None when degenerate.

    Prefers the explicit ``bounds`` block from the contract; falls back to the
    geometry's own extents when it's missing or unusable.
    """
    raw = (scene_json or {}).get("bounds") or {}
    bx = (_num(raw.get("min_x")), _num(raw.get("min_y")),
          _num(raw.get("max_x")), _num(raw.get("max_y")))
    have_raw = any(k in raw for k in ("min_x", "min_y", "max_x", "max_y"))

    pts = _collect_points(scene_json)
    if pts:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        gx = (min(xs), min(ys), max(xs), max(ys))
    else:
        gx = None

    # Choose whichever source actually spans some area.
    candidates = []
    if have_raw:
        candidates.append(bx)
    if gx is not None:
        candidates.append(gx)
    for min_x, min_y, max_x, max_y in candidates:
        if (max_x - min_x) > 1e-9 or (max_y - min_y) > 1e-9:
            return min_x, min_y, max_x, max_y
    return None


# --------------------------------------------------------------------------- #
# Fonts / text
# --------------------------------------------------------------------------- #
def _font(size):
    """A TrueType font at *size*, falling back to PIL's default bitmap font."""
    size = int(max(8, size))
    for name in ("arial.ttf", "Arial.ttf", "DejaVuSans.ttf",
                 "LiberationSans-Regular.ttf", "segoeui.ttf", "Helvetica.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow: load_default() takes no size
        return ImageFont.load_default()


def _font_bold(size):
    """A bold TrueType font at *size* (falls back to the regular face)."""
    size = int(max(8, size))
    for name in ("arialbd.ttf", "Arial-Bold.ttf", "DejaVuSans-Bold.ttf",
                 "LiberationSans-Bold.ttf", "segoeuib.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    return _font(size)


def _text_size(draw, text, font):
    """(w, h) of *text*, robust across Pillow versions."""
    try:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        return right - left, bottom - top
    except Exception:  # pragma: no cover - extremely defensive
        return (len(text) * 8, 16)


def _text_centered(draw, cx, cy, text, font, fill=_INK):
    """Draw *text* centred on (cx, cy)."""
    w, h = _text_size(draw, text, font)
    draw.text((cx - w / 2.0, cy - h / 2.0), text, fill=fill, font=font)


def _fmt_m(value):
    """Format a length in meters, e.g. 3.0 -> '3.00 m'."""
    return f"{_num(value):.2f} m"


def _fmt_area(value):
    """Format an area in m2, e.g. 20.0 -> '20.00 m2'."""
    return f"{_num(value):.2f} m2"


# --------------------------------------------------------------------------- #
# Empty / placeholder sheet
# --------------------------------------------------------------------------- #
def _empty_image(size):
    """A white sheet stamped 'Sin geometria' (nothing meaningful to draw)."""
    img = Image.new("RGB", size, _BG)
    draw = ImageDraw.Draw(img)
    _draw_frame(draw, size)
    msg = "Sin geometria"
    font = _font(max(28, size[1] // 18))
    _text_centered(draw, size[0] / 2.0, size[1] / 2.0, msg, font, fill=_GREY)
    return img


def _draw_frame(draw, size, inset=40):
    """The technical drawing border (double rule)."""
    w, h = size
    draw.rectangle([inset, inset, w - inset, h - inset], outline=_INK, width=3)
    draw.rectangle([inset + 8, inset + 8, w - inset - 8, h - inset - 8],
                   outline=_INK, width=1)


# --------------------------------------------------------------------------- #
# Projection: world meters -> screen pixels (Y flipped so north is up)
# --------------------------------------------------------------------------- #
def _make_projector(bounds, canvas_w, canvas_h, margin, top_margin):
    """Return (project(x, y) -> (px, py), scale_px_per_m) fitting *bounds*.

    Keeps aspect ratio, centres the drawing, and flips Y so the building reads
    with north up (world y grows up; screen y grows down).
    """
    min_x, min_y, max_x, max_y = bounds
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)

    avail_w = max(canvas_w - 2 * margin, 1)
    avail_h = max(canvas_h - top_margin - margin, 1)
    scale = min(avail_w / span_x, avail_h / span_y)

    draw_w = span_x * scale
    draw_h = span_y * scale
    off_x = (canvas_w - draw_w) / 2.0
    off_y = top_margin + (avail_h - draw_h) / 2.0

    def project(x, y):
        # Flip Y: world (min_y..max_y) -> screen (bottom..top).
        return off_x + (x - min_x) * scale, off_y + (max_y - y) * scale

    return project, scale


# --------------------------------------------------------------------------- #
# Geometry math
# --------------------------------------------------------------------------- #
def _point_segment_dist(p, a, b):
    """Distance from point *p* to segment *a*-*b* (all px tuples)."""
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    if seg2 <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / seg2
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def _nearest_wall(scene_json, project, pos):
    """Return (a_px, b_px, thickness_m) of the wall nearest *pos* (world)."""
    px, py = project(*pos)
    best = None
    best_d = float("inf")
    for wall in _walls(scene_json):
        a = project(*_point(wall.get("start")))
        b = project(*_point(wall.get("end")))
        d = _point_segment_dist((px, py), a, b)
        if d < best_d:
            best_d = d
            best = (a, b, _num(wall.get("thickness"), 0.12) or 0.12)
    return best


def _opening_axis(scene_json, project, pos):
    """(unit_along, unit_normal) of the wall nearest *pos*, in pixel space.

    Lets openings be drawn *along* their wall. Falls back to horizontal.
    """
    near = _nearest_wall(scene_json, project, pos)
    if near is None:
        return (1.0, 0.0), (0.0, 1.0)
    (ax, ay), (bx, by), _t = near
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return (1.0, 0.0), (0.0, 1.0)
    ux, uy = dx / length, dy / length
    return (ux, uy), (-uy, ux)


def _wall_px(thickness_m, scale):
    """A wall thickness in meters mapped to a clamped on-screen pixel width."""
    return max(_MIN_THICKNESS_PX,
               min(_MAX_THICKNESS_PX, (thickness_m or 0.12) * scale))


# --------------------------------------------------------------------------- #
# Walls (filled black rectangles with real thickness)
# --------------------------------------------------------------------------- #
def _rect_polygon(p1, p2, thickness_px):
    """Four corners of a rectangle: segment p1-p2 inflated by thickness_px."""
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return None
    nx, ny = -dy / length, dx / length
    h = thickness_px / 2.0
    return [
        (x1 + nx * h, y1 + ny * h),
        (x2 + nx * h, y2 + ny * h),
        (x2 - nx * h, y2 - ny * h),
        (x1 - nx * h, y1 - ny * h),
    ]


def _draw_wall(draw, p1, p2, thickness_px):
    """A wall as a solid black rectangle with crisp outline (AutoCAD style).

    Square ends overlap a little at corners so junctions read as solid.
    """
    poly = _rect_polygon(p1, p2, thickness_px)
    if poly is None:
        return
    draw.polygon(poly, fill=_INK, outline=_INK)
    # Square caps (extend half a thickness) keep corners filled without gaps.
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length > 1e-9:
        ux, uy = dx / length, dy / length
        ext = thickness_px / 2.0
        cap = _rect_polygon((x1 - ux * ext, y1 - uy * ext),
                            (x2 + ux * ext, y2 + uy * ext), thickness_px)
        if cap is not None:
            draw.polygon(cap, fill=_INK, outline=_INK)


# --------------------------------------------------------------------------- #
# Doors: opening gap + 90-degree swing arc
# --------------------------------------------------------------------------- #
def _draw_door(draw, scene_json, project, scale, door, fallback_t_px):
    """A door as a white wall gap + leaf line + 90-degree quarter-circle arc."""
    pos = _point(door.get("position"))
    cx, cy = project(*pos)
    width_m = _num(door.get("width"), 0.9) or 0.9
    near = _nearest_wall(scene_json, project, pos)
    t_px = _wall_px(near[2], scale) if near else fallback_t_px
    half = max(width_m * scale / 2.0, t_px)
    (ux, uy), (nx, ny) = _opening_axis(scene_json, project, pos)

    p1 = (cx - ux * half, cy - uy * half)
    p2 = (cx + ux * half, cy + uy * half)

    # Punch a white gap (a touch wider than the wall) so the jamb reads clean.
    gap = _rect_polygon(p1, p2, t_px + 2.0)
    if gap is not None:
        draw.polygon(gap, fill=_BG, outline=_BG)

    # Jamb ticks across the wall at each side of the opening (thin black lines).
    for jp in (p1, p2):
        draw.line([(jp[0] + nx * t_px / 2.0, jp[1] + ny * t_px / 2.0),
                   (jp[0] - nx * t_px / 2.0, jp[1] - ny * t_px / 2.0)],
                  fill=_INK, width=2)

    # Door leaf: from one jamb (p1) swinging out along the normal.
    leaf_len = 2 * half
    leaf_end = (p1[0] + nx * leaf_len, p1[1] + ny * leaf_len)
    draw.line([p1, leaf_end], fill=_INK, width=2)

    # 90-degree swing arc from the open leaf round to the closed position.
    bbox = [p1[0] - leaf_len, p1[1] - leaf_len,
            p1[0] + leaf_len, p1[1] + leaf_len]
    a_open = math.degrees(math.atan2(ny, nx))
    a_closed = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))
    diff = ((a_closed - a_open + 180) % 360) - 180
    start, end = (a_open, a_open + diff) if diff >= 0 else (a_open + diff, a_open)
    try:
        draw.arc(bbox, start, end, fill=_INK, width=1)
    except Exception:  # pragma: no cover - degenerate bbox guard
        pass


# --------------------------------------------------------------------------- #
# Windows: technical triple-line symbol inside the vano
# --------------------------------------------------------------------------- #
def _draw_window(draw, scene_json, project, scale, window, fallback_t_px):
    """A window as the conventional triple line spanning the opening (vano)."""
    pos = _point(window.get("position"))
    cx, cy = project(*pos)
    width_m = _num(window.get("width"), 1.0) or 1.0
    near = _nearest_wall(scene_json, project, pos)
    t_px = _wall_px(near[2], scale) if near else fallback_t_px
    half = max(width_m * scale / 2.0, t_px)
    (ux, uy), (nx, ny) = _opening_axis(scene_json, project, pos)

    p1 = (cx - ux * half, cy - uy * half)
    p2 = (cx + ux * half, cy + uy * half)

    # White gap over the wall, then the triple line (two rails + centre).
    gap = _rect_polygon(p1, p2, t_px + 2.0)
    if gap is not None:
        draw.polygon(gap, fill=_BG, outline=_BG)

    off = max(t_px * 0.30, 2.0)
    for sign in (-1.0, 1.0):  # the two outer rails (wall faces)
        q1 = (p1[0] + nx * off * sign, p1[1] + ny * off * sign)
        q2 = (p2[0] + nx * off * sign, p2[1] + ny * off * sign)
        draw.line([q1, q2], fill=_INK, width=2)
    draw.line([p1, p2], fill=_INK, width=1)  # centre line (the glass)

    for jp in (p1, p2):  # jamb caps across the band
        draw.line([(jp[0] + nx * off, jp[1] + ny * off),
                   (jp[0] - nx * off, jp[1] - ny * off)],
                  fill=_INK, width=2)


# --------------------------------------------------------------------------- #
# Room labels (name + area, centred)
# --------------------------------------------------------------------------- #
def _draw_rooms(draw, scene_json, project, scale, name_font, area_font):
    """Centre each room's name + area on its centroid."""
    for room in _rooms(scene_json):
        cx, cy = project(_num(room.get("x")), _num(room.get("y")))
        name = str(room.get("name") or "Ambiente").upper()
        area = room.get("area")
        if area is None:
            w, h = _num(room.get("w")), _num(room.get("h"))
            area = w * h
        _text_centered(draw, cx, cy - 12, name, name_font, fill=_INK)
        _text_centered(draw, cx, cy + 12, _fmt_area(area), area_font, fill=_INK)


# --------------------------------------------------------------------------- #
# Dimension lines (cotas)
# --------------------------------------------------------------------------- #
def _arrow_head(draw, tip, ang, size=9):
    """A small filled arrow head at *tip* pointing along angle *ang* (rad)."""
    a1 = ang + math.radians(160)
    a2 = ang - math.radians(160)
    p1 = (tip[0] + size * math.cos(a1), tip[1] + size * math.sin(a1))
    p2 = (tip[0] + size * math.cos(a2), tip[1] + size * math.sin(a2))
    draw.polygon([tip, p1, p2], fill=_DIM)


def _dim_horizontal(draw, x1, x2, y, value_m, font, *, ext_from=None, flip=False):
    """A horizontal dimension line from x1 to x2 at screen height *y*.

    ``ext_from`` (a y) draws extension (witness) lines back to the geometry.
    """
    if abs(x2 - x1) < 2:
        return
    draw.line([(x1, y), (x2, y)], fill=_DIM, width=1)
    _arrow_head(draw, (x1, y), math.atan2(0, x1 - x2))
    _arrow_head(draw, (x2, y), math.atan2(0, x2 - x1))
    if ext_from is not None:
        draw.line([(x1, ext_from), (x1, y)], fill=_DIM, width=1)
        draw.line([(x2, ext_from), (x2, y)], fill=_DIM, width=1)
    label = _fmt_m(value_m)
    w, h = _text_size(draw, label, font)
    ty = y - h - 4 if not flip else y + 4
    # White backing so the number stays legible over lines.
    mx = (x1 + x2) / 2.0
    draw.rectangle([mx - w / 2.0 - 3, ty - 2, mx + w / 2.0 + 3, ty + h + 2],
                   fill=_BG)
    draw.text((mx - w / 2.0, ty), label, fill=_DIM, font=font)


def _dim_vertical(draw, y1, y2, x, value_m, font, *, ext_from=None, flip=False):
    """A vertical dimension line from y1 to y2 at screen x position *x*."""
    if abs(y2 - y1) < 2:
        return
    draw.line([(x, y1), (x, y2)], fill=_DIM, width=1)
    _arrow_head(draw, (x, y1), math.atan2(y1 - y2, 0))
    _arrow_head(draw, (x, y2), math.atan2(y2 - y1, 0))
    if ext_from is not None:
        draw.line([(ext_from, y1), (x, y1)], fill=_DIM, width=1)
        draw.line([(ext_from, y2), (x, y2)], fill=_DIM, width=1)
    label = _fmt_m(value_m)
    w, h = _text_size(draw, label, font)
    tx = x - w - 6 if not flip else x + 6
    my = (y1 + y2) / 2.0
    draw.rectangle([tx - 3, my - h / 2.0 - 2, tx + w + 3, my + h / 2.0 + 2],
                   fill=_BG)
    draw.text((tx, my - h / 2.0), label, fill=_DIM, font=font)


def _draw_dimensions(draw, scene_json, bounds, project, scale, font):
    """Overall width/height cotas + a per-room cota on the main ambiente."""
    min_x, min_y, max_x, max_y = bounds

    # Screen corners of the bounding box (Y flipped).
    tl = project(min_x, max_y)   # top-left on screen
    br = project(max_x, min_y)   # bottom-right on screen
    left_x, top_y = tl[0], tl[1]
    right_x, bot_y = br[0], br[1]

    gap = 46  # how far the cota sits outside the geometry

    # Overall WIDTH below the plan.
    _dim_horizontal(draw, left_x, right_x, bot_y + gap, max_x - min_x, font,
                    ext_from=bot_y, flip=True)
    # Overall HEIGHT (length) to the left of the plan.
    _dim_vertical(draw, top_y, bot_y, left_x - gap, max_y - min_y, font,
                  ext_from=left_x)

    # Per-room cota: pick the largest room and dimension its width on top.
    rooms = _rooms(scene_json)
    if rooms:
        main = max(rooms, key=lambda r: _num(r.get("area"),
                                             _num(r.get("w")) * _num(r.get("h"))))
        cx, cy = _num(main.get("x")), _num(main.get("y"))
        w, h = _num(main.get("w")), _num(main.get("h"))
        if w > 1e-6 and h > 1e-6:
            r_tl = project(cx - w / 2.0, cy + h / 2.0)
            r_br = project(cx + w / 2.0, cy - h / 2.0)
            _dim_horizontal(draw, r_tl[0], r_br[0], top_y - gap, w, font,
                            ext_from=top_y)
            _dim_vertical(draw, r_tl[1], r_br[1], right_x + gap, h, font,
                          flip=True, ext_from=right_x)


# --------------------------------------------------------------------------- #
# North arrow + scale note
# --------------------------------------------------------------------------- #
def _draw_north(draw, x, y, r, font):
    """A north arrow (points up) with an 'N' label, top-right corner."""
    draw.ellipse([x - r, y - r, x + r, y + r], outline=_INK, width=2)
    tip = (x, y - r - 14)
    base_l = (x - r * 0.55, y + r * 0.35)
    base_r = (x + r * 0.55, y + r * 0.35)
    mid = (x, y)
    draw.polygon([tip, base_l, mid], fill=_INK)            # filled half
    draw.polygon([tip, base_r, mid], outline=_INK)         # hollow half
    w, h = _text_size(draw, "N", font)
    draw.text((x - w / 2.0, y - r - 14 - h - 6), "N", fill=_INK, font=font)


def _draw_scale_note(draw, x, y, font):
    """The conventional scale note (technical drawings reference 1:100)."""
    draw.text((x, y), "ESC. 1:100", fill=_INK, font=font)


# --------------------------------------------------------------------------- #
# Areas table (cuadro de areas)
# --------------------------------------------------------------------------- #
def _draw_area_table(draw, scene_json, x, y, font, head_font):
    """A boxed table of rooms with their area + a total, bottom-left corner."""
    rooms = _rooms(scene_json)
    rows = []
    total = 0.0
    for room in rooms:
        name = str(room.get("name") or "Ambiente").upper()
        area = room.get("area")
        if area is None:
            area = _num(room.get("w")) * _num(room.get("h"))
        area = _num(area)
        total += area
        rows.append((name, _fmt_area(area)))

    title = "CUADRO DE AREAS"
    line_h = _text_size(draw, "Ag", font)[1] + 10
    head_h = _text_size(draw, title, head_font)[1] + 12

    # Width: fit the longest name + area column.
    name_w = max([_text_size(draw, r[0], font)[0] for r in rows] +
                 [_text_size(draw, "AMBIENTE", font)[0]] +
                 [_text_size(draw, "AREA TOTAL", font)[0]])
    area_w = max([_text_size(draw, r[1], font)[0] for r in rows] +
                 [_text_size(draw, "AREA", font)[0],
                  _text_size(draw, _fmt_area(total), font)[0]])
    pad = 14
    col_gap = 26
    tbl_w = pad * 2 + name_w + col_gap + area_w
    n_rows = len(rows) + 1  # + the AREA TOTAL row
    tbl_h = head_h + line_h * (n_rows + 1)  # + header row

    # White backing so the table stays legible over any geometry, then box.
    draw.rectangle([x, y, x + tbl_w, y + tbl_h], fill=_BG)
    # Outer box + header band.
    draw.rectangle([x, y, x + tbl_w, y + tbl_h], outline=_INK, width=2)
    draw.rectangle([x, y, x + tbl_w, y + head_h], outline=_INK, width=2)
    _text_centered(draw, x + tbl_w / 2.0, y + head_h / 2.0, title, head_font)

    cy = y + head_h
    name_x = x + pad
    area_x = x + pad + name_w + col_gap

    # Column header row.
    draw.text((name_x, cy + 5), "AMBIENTE", fill=_INK, font=font)
    draw.text((area_x, cy + 5), "AREA", fill=_INK, font=font)
    cy += line_h
    draw.line([(x, cy), (x + tbl_w, cy)], fill=_INK, width=1)

    for name, area_str in rows:
        draw.text((name_x, cy + 5), name, fill=_INK, font=font)
        draw.text((area_x, cy + 5), area_str, fill=_INK, font=font)
        cy += line_h
        draw.line([(x, cy), (x + tbl_w, cy)], fill=_GREY, width=1)

    # Total row (bold).
    draw.text((name_x, cy + 5), "AREA TOTAL", fill=_INK, font=head_font)
    draw.text((area_x, cy + 5), _fmt_area(total), fill=_INK, font=head_font)

    # Column separator.
    sep_x = area_x - col_gap / 2.0
    draw.line([(sep_x, y + head_h), (sep_x, y + tbl_h)], fill=_GREY, width=1)


# --------------------------------------------------------------------------- #
# Plan composition
# --------------------------------------------------------------------------- #
def _render_plan(scene_json, canvas_w, canvas_h, margin, *, title=None):
    """Draw the full technical plan onto a fresh RGB image and return it."""
    bounds = _bounds(scene_json)
    if bounds is None:
        return _empty_image((canvas_w, canvas_h))

    img = Image.new("RGB", (canvas_w, canvas_h), _BG)
    draw = ImageDraw.Draw(img)

    _draw_frame(draw, (canvas_w, canvas_h))

    top_margin = margin
    if title:
        font = _font_bold(max(26, canvas_h // 34))
        tw, th = _text_size(draw, title, font)
        draw.text(((canvas_w - tw) / 2.0, margin // 2), title,
                  fill=_INK, font=font)
        top_margin = margin + th + 10

    # Leave room around the geometry for cotas, table, north arrow.
    plan_margin = margin + 30
    project, scale = _make_projector(
        bounds, canvas_w, canvas_h, plan_margin, top_margin)

    # 1) Walls (solid black rectangles, real thickness).
    walls = _walls(scene_json)
    for wall in walls:
        p1 = project(*_point(wall.get("start")))
        p2 = project(*_point(wall.get("end")))
        if p1 == p2:
            continue
        thickness_m = _num(wall.get("thickness"), 0.12) or 0.12
        _draw_wall(draw, p1, p2, _wall_px(thickness_m, scale))

    # A representative wall thickness drives opening fallbacks.
    if walls:
        rep_t = _wall_px(
            sorted(_num(w.get("thickness"), 0.12) or 0.12 for w in walls)[len(walls) // 2],
            scale)
    else:
        rep_t = _MIN_THICKNESS_PX

    # 2) Openings (windows then doors so swing arcs sit on top).
    for window in _windows(scene_json):
        _draw_window(draw, scene_json, project, scale, window, rep_t)
    for door in _doors(scene_json):
        _draw_door(draw, scene_json, project, scale, door, rep_t)

    # 3) Room labels.
    name_font = _font_bold(max(16, int(min(canvas_w, canvas_h) / 46)))
    area_font = _font(max(13, int(min(canvas_w, canvas_h) / 60)))
    _draw_rooms(draw, scene_json, project, scale, name_font, area_font)

    # 4) Dimension lines (cotas).
    dim_font = _font(max(13, int(min(canvas_w, canvas_h) / 64)))
    _draw_dimensions(draw, scene_json, bounds, project, scale, dim_font)

    # 5) North arrow (top-right) + scale note.
    n_font = _font_bold(max(18, int(min(canvas_w, canvas_h) / 44)))
    nx = canvas_w - margin - 30
    ny = top_margin + 60
    _draw_north(draw, nx, ny, max(20, int(min(canvas_w, canvas_h) / 44)), n_font)
    _draw_scale_note(draw, nx - 70, ny + 60,
                     _font(max(15, int(min(canvas_w, canvas_h) / 56))))

    # 6) Areas table (bottom-left), only when rooms are present.
    if _rooms(scene_json):
        tbl_font = _font(max(13, int(min(canvas_w, canvas_h) / 62)))
        tbl_head = _font_bold(max(14, int(min(canvas_w, canvas_h) / 56)))
        try:
            # Pre-measure height to anchor at the bottom-left inside the frame.
            n = len(_rooms(scene_json)) + 2
            line_h = _text_size(draw, "Ag", tbl_font)[1] + 10
            head_h = _text_size(draw, "CUADRO DE AREAS", tbl_head)[1] + 12
            tbl_h = head_h + line_h * (n + 1)
            tx = margin + 6
            ty = canvas_h - margin - tbl_h
            _draw_area_table(draw, scene_json, tx, ty, tbl_font, tbl_head)
        except Exception:  # pragma: no cover - never let the table break the plan
            pass

    return img


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def render_png(scene_json: dict) -> bytes:
    """Render the scene as a top-down technical plan PNG (bytes).

    Always returns valid PNG bytes (magic ``89 50 4E 47``); an empty/degenerate
    scene yields a white sheet stamped "Sin geometria".
    """
    img = _render_plan(scene_json, _CANVAS, _CANVAS_H, _MARGIN)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    data = buf.getvalue()
    assert data[:4] == b"\x89PNG", "render_png did not produce PNG bytes"
    return data


def render_pdf(scene_json: dict) -> bytes:
    """Render the scene as a landscape A4 print-quality PDF (bytes).

    Uses reportlab when available (embedded raster plan + document title), else
    falls back to Pillow's built-in PDF writer. Always returns bytes starting
    with ``%PDF``.
    """
    title = "Arketo - Plano Arquitectonico 2D"
    page_w, page_h = _A4_LANDSCAPE_PX
    img = _render_plan(scene_json, page_w, page_h, _MARGIN, title=title)

    data = _pdf_with_reportlab(img, title)
    if not data or not data.startswith(b"%PDF"):
        data = _pdf_with_pillow(img)

    assert data.startswith(b"%PDF"), "render_pdf did not produce PDF bytes"
    return data


def _pdf_with_pillow(img: Image.Image) -> bytes:
    """Embed *img* as a single A4-landscape page via Pillow's PDF writer."""
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=float(_PDF_DPI))
    return buf.getvalue()


def _pdf_with_reportlab(img: Image.Image, title: str):
    """Vector PDF (raster plan + title) via reportlab, or None if unavailable."""
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.units import inch
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas as pdf_canvas
    except Exception:
        return None

    try:
        page_w, page_h = landscape(A4)
        buf = io.BytesIO()
        c = pdf_canvas.Canvas(buf, pagesize=(page_w, page_h))

        pad = 0.35 * inch
        avail_w = page_w - 2 * pad
        avail_h = page_h - 2 * pad
        iw, ih = img.size
        ratio = min(avail_w / iw, avail_h / ih)
        draw_w, draw_h = iw * ratio, ih * ratio
        x = (page_w - draw_w) / 2.0
        y = (page_h - draw_h) / 2.0

        c.drawImage(ImageReader(img), x, y, width=draw_w, height=draw_h,
                    preserveAspectRatio=True, mask="auto")
        c.setTitle(title)
        c.showPage()
        c.save()
        return buf.getvalue()
    except Exception:
        return None
