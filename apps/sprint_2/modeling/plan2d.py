"""Render a clean architectural 2D floor plan (top-down) from a scene dict.

The input is the same ``scene_json`` produced for the 3D model (see ``glb.py``):

    {
        "walls":   [{"start": {"x", "y"}, "end": {"x", "y"},
                     "thickness": m, "height": m}, ...],
        "doors":   [{"position": {"x", "y"}, "width": m}, ...],
        "windows": [{"position": {"x", "y"}, "width": m}, ...],
    }

Coordinates may be normalized (~0..1) or in meters; we only ever *fit* the
scene's bounding box into the canvas, so either works without configuration.
The plan view is the plan's ground plane (x, y) drawn straight onto the page:
x -> right, y -> down (image convention), with the aspect ratio preserved.

Two entry points:

* ``render_png(scene_json) -> bytes`` : a top-down plan PNG (~1600px).
* ``render_pdf(scene_json) -> bytes`` : the same plan as a landscape A4 PDF.

Both are defensive: missing keys, ``None`` values, empty/degenerate geometry,
and odd numbers never raise — at worst you get a white sheet that says
"Sin geometria". Returned bytes always carry a valid magic number
(PNG: ``89 50 4E 47``; PDF: ``%PDF``).
"""

from __future__ import annotations

import io
import math

from PIL import Image, ImageDraw, ImageFont

# --- Canvas / layout -------------------------------------------------------
_CANVAS = 1600          # longest side of the PNG drawing area (px)
_MARGIN = 120           # white border around the plan (px)
_MIN_THICKNESS_PX = 6   # walls are never thinner than this on screen
_MAX_THICKNESS_PX = 60  # ...nor absurdly thick when the scene is tiny

# --- Colours (clean, printable architectural palette) ----------------------
_BG = (255, 255, 255)
_WALL = (25, 25, 25)
_WALL_EDGE = (0, 0, 0)
_DOOR = (140, 74, 30)        # warm brown
_WINDOW = (38, 110, 190)     # blue
_TITLE = (40, 40, 40)
_SUBTLE = (120, 120, 120)

# --- PDF page (landscape, 150 DPI gives crisp print) -----------------------
_PDF_DPI = 150
_A4_LANDSCAPE_PX = (1754, 1240)   # 297 x 210 mm @ 150 DPI


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #
def _num(value, default=0.0):
    """Coerce *value* to float, tolerating None / strings / junk."""
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


def _collect_points(scene_json):
    """Every (x, y) that contributes to the plan (wall ends + openings)."""
    pts = []
    for wall in _walls(scene_json):
        pts.append(_point(wall.get("start")))
        pts.append(_point(wall.get("end")))
    for opening in list(_doors(scene_json)) + list(_windows(scene_json)):
        pts.append(_point(opening.get("position")))
    return pts


def _bounds(scene_json):
    """(min_x, min_y, max_x, max_y) of the scene, or None when empty/degenerate."""
    pts = _collect_points(scene_json)
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if (max_x - min_x) <= 1e-9 and (max_y - min_y) <= 1e-9:
        return None
    return min_x, min_y, max_x, max_y


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


def _text_size(draw, text, font):
    """(w, h) of *text*, robust across Pillow versions."""
    try:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        return right - left, bottom - top
    except Exception:  # pragma: no cover - extremely defensive
        return (len(text) * 8, 16)


# --------------------------------------------------------------------------- #
# Empty / placeholder sheet
# --------------------------------------------------------------------------- #
def _empty_image(size):
    """A white sheet stamped 'Sin geometria' (used when there's nothing to draw)."""
    img = Image.new("RGB", size, _BG)
    draw = ImageDraw.Draw(img)
    msg = "Sin geometria"
    font = _font(max(28, size[1] // 18))
    w, h = _text_size(draw, msg, font)
    draw.text(((size[0] - w) / 2.0, (size[1] - h) / 2.0), msg,
              fill=_SUBTLE, font=font)
    return img


# --------------------------------------------------------------------------- #
# Projection (fit plan bounds into the canvas, preserving aspect ratio)
# --------------------------------------------------------------------------- #
def _make_projector(bounds, canvas_w, canvas_h, side_margin, top_margin=None):
    """Return (project(x, y) -> (px, py), scale) fitting *bounds* into the canvas.

    Keeps aspect ratio and centres the drawing. ``top_margin`` (when given) lets
    a title sit above the plan without overlapping it. Y is *not* flipped: the
    plan reads the same way it does in the 3D scene (y grows downward on screen).
    """
    if top_margin is None:
        top_margin = side_margin
    min_x, min_y, max_x, max_y = bounds
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)

    avail_w = max(canvas_w - 2 * side_margin, 1)
    avail_h = max(canvas_h - top_margin - side_margin, 1)
    scale = min(avail_w / span_x, avail_h / span_y)

    draw_w = span_x * scale
    draw_h = span_y * scale
    off_x = (canvas_w - draw_w) / 2.0
    off_y = top_margin + (avail_h - draw_h) / 2.0

    def project(x, y):
        return off_x + (x - min_x) * scale, off_y + (y - min_y) * scale

    return project, scale


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


def _opening_axis(scene_json, project, pos):
    """Direction (unit) + normal of the wall nearest *pos*, in pixel space.

    Lets doors/windows be drawn *along* the wall they sit on. Falls back to a
    horizontal axis when no wall is available.
    """
    px, py = project(*pos)
    best = None
    best_d = float("inf")
    for wall in _walls(scene_json):
        a = project(*_point(wall.get("start")))
        b = project(*_point(wall.get("end")))
        d = _point_segment_dist((px, py), a, b)
        if d < best_d:
            best_d = d
            best = (a, b)
    if best is None:
        return (1.0, 0.0), (0.0, 1.0)
    (ax, ay), (bx, by) = best
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return (1.0, 0.0), (0.0, 1.0)
    ux, uy = dx / length, dy / length
    return (ux, uy), (-uy, ux)


# --------------------------------------------------------------------------- #
# Element drawing
# --------------------------------------------------------------------------- #
def _draw_wall(draw, p1, p2, thickness_px):
    """A thick wall segment with rounded ends + crisp black centre edge."""
    width = max(1, int(round(thickness_px)))
    draw.line([p1, p2], fill=_WALL, width=width, joint="curve")
    r = thickness_px / 2.0
    for (cx, cy) in (p1, p2):  # rounded caps so corners join cleanly
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_WALL)
    draw.line([p1, p2], fill=_WALL_EDGE, width=1)


def _draw_door(draw, scene_json, project, scale, door, wall_px):
    """A door as a wall gap + a quarter-circle swing arc (brown)."""
    pos = _point(door.get("position"))
    cx, cy = project(*pos)
    width_m = _num(door.get("width"), 0.9) or 0.9
    half = max(width_m * scale / 2.0, wall_px)
    (ux, uy), (nx, ny) = _opening_axis(scene_json, project, pos)

    p1 = (cx - ux * half, cy - uy * half)
    p2 = (cx + ux * half, cy + uy * half)

    # Clear the wall under the opening (white gap) so the door reads as a hole.
    draw.line([p1, p2], fill=_BG, width=int(round(wall_px + 2)))

    # Door leaf: a line from one jamb swinging out along the wall normal.
    leaf_len = 2 * half
    leaf_end = (p1[0] + nx * leaf_len, p1[1] + ny * leaf_len)
    draw.line([p1, leaf_end], fill=_DOOR, width=max(3, int(wall_px * 0.5)))

    # Swing arc: a 90-degree quarter circle from the open leaf (along the
    # normal) round to the closed position (toward the far jamb p2).
    bbox = [p1[0] - leaf_len, p1[1] - leaf_len,
            p1[0] + leaf_len, p1[1] + leaf_len]
    a_open = math.degrees(math.atan2(ny, nx))               # leaf, swung open
    a_closed = math.degrees(math.atan2(p2[1] - p1[1],       # leaf, closed
                                       p2[0] - p1[0]))
    # Pick the +/-90 sweep direction that connects open -> closed.
    diff = ((a_closed - a_open + 180) % 360) - 180
    start, end = (a_open, a_open + diff) if diff >= 0 else (a_open + diff, a_open)
    try:
        draw.arc(bbox, start, end, fill=_DOOR, width=max(2, int(wall_px * 0.3)))
    except Exception:  # pragma: no cover - guard against a degenerate bbox
        pass

    for jp in (p1, p2):  # jamb ticks so the opening edges read crisply
        draw.ellipse([jp[0] - 3, jp[1] - 3, jp[0] + 3, jp[1] + 3], fill=_DOOR)


def _draw_window(draw, scene_json, project, scale, window, wall_px):
    """A window as a blue glazing band (parallel lines) spanning the opening."""
    pos = _point(window.get("position"))
    cx, cy = project(*pos)
    width_m = _num(window.get("width"), 1.0) or 1.0
    half = max(width_m * scale / 2.0, wall_px)
    (ux, uy), (nx, ny) = _opening_axis(scene_json, project, pos)

    p1 = (cx - ux * half, cy - uy * half)
    p2 = (cx + ux * half, cy + uy * half)

    # Clear the wall, then draw the glazing (centre line + two parallel rails).
    draw.line([p1, p2], fill=_BG, width=int(round(wall_px + 2)))
    off = max(wall_px * 0.28, 2.0)
    for sign in (-1.0, 1.0):
        q1 = (p1[0] + nx * off * sign, p1[1] + ny * off * sign)
        q2 = (p2[0] + nx * off * sign, p2[1] + ny * off * sign)
        draw.line([q1, q2], fill=_WINDOW, width=2)
    draw.line([p1, p2], fill=_WINDOW, width=2)
    for jp in (p1, p2):  # frame ends (a short tick across the band)
        draw.line([(jp[0] + nx * off, jp[1] + ny * off),
                   (jp[0] - nx * off, jp[1] - ny * off)],
                  fill=_WINDOW, width=2)


# --------------------------------------------------------------------------- #
# Plan composition
# --------------------------------------------------------------------------- #
def _render_plan(scene_json, canvas_w, canvas_h, margin, *, title=None):
    """Draw the full plan onto a fresh RGB image and return it.

    Returns the 'Sin geometria' sheet when there's nothing meaningful to draw.
    """
    bounds = _bounds(scene_json)
    if bounds is None:
        return _empty_image((canvas_w, canvas_h))

    img = Image.new("RGB", (canvas_w, canvas_h), _BG)
    draw = ImageDraw.Draw(img)

    top_margin = margin
    if title:
        font = _font(max(26, canvas_h // 30))
        tw, th = _text_size(draw, title, font)
        draw.text(((canvas_w - tw) / 2.0, margin // 3), title,
                  fill=_TITLE, font=font)
        top_margin = margin + th  # keep the plan clear of the title

    project, scale = _make_projector(
        bounds, canvas_w, canvas_h, margin, top_margin)

    # Walls first (so openings can punch white gaps over them).
    walls = _walls(scene_json)
    for wall in walls:
        p1 = project(*_point(wall.get("start")))
        p2 = project(*_point(wall.get("end")))
        if p1 == p2:
            continue
        thickness_m = _num(wall.get("thickness"), 0.15) or 0.15
        t_px = max(_MIN_THICKNESS_PX, min(_MAX_THICKNESS_PX, thickness_m * scale))
        _draw_wall(draw, p1, p2, t_px)

    # A representative wall thickness drives opening gap widths.
    if walls:
        thicks = sorted(
            max(_MIN_THICKNESS_PX,
                min(_MAX_THICKNESS_PX,
                    (_num(w.get("thickness"), 0.15) or 0.15) * scale))
            for w in walls
        )
        rep_t = thicks[len(thicks) // 2]
    else:
        rep_t = _MIN_THICKNESS_PX

    for window in _windows(scene_json):
        _draw_window(draw, scene_json, project, scale, window, rep_t)
    for door in _doors(scene_json):
        _draw_door(draw, scene_json, project, scale, door, rep_t)

    return img


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def render_png(scene_json: dict) -> bytes:
    """Render the scene as a top-down architectural plan PNG (bytes).

    Always returns valid PNG bytes (magic ``89 50 4E 47``); an empty/degenerate
    scene yields a white sheet stamped "Sin geometria".
    """
    img = _render_plan(scene_json, _CANVAS, _CANVAS, _MARGIN)
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
    title = "Arketo - Plano 2D"
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

        # Fit the raster plan into the printable area, preserving aspect ratio.
        pad = 0.4 * inch
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
