"""Deterministic mock design provider (no API key needed).

Parses the brief (footprint, #bedrooms, #bathrooms) and generates a *procedural
multi-room house* — outer shell, a public/private split, bedrooms+baths with real
doorway gaps, a kitchen partition and perimeter windows — instead of a bare box.
Output is the same normalized scene schema used by detection/3D, so it flows into
the GLB builder and the 2D plan render. Lets CU9 work end-to-end offline.
"""

from __future__ import annotations

import re

from django.conf import settings

from .base import DesignProviderBase

_SIZE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:x|por|×)\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
_M_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*m(?:etros|²|2)?\b", re.IGNORECASE)
_AREA_RE = re.compile(r"(\d{2,4})\s*m(?:²|2)\b", re.IGNORECASE)
_NUM_WORDS = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4,
              "cinco": 5, "seis": 6, "siete": 7, "ocho": 8}


def _to_float(value: str) -> float:
    return float(value.replace(",", "."))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(v, hi))


def _count(prompt: str, kw_regex: str, default: int) -> int:
    p = (prompt or "").lower()
    m = re.search(
        r"(\d+|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho)\s+(?:[a-záéíóúñ]+\s+){0,3}?(?:"
        + kw_regex + ")", p)
    if not m:
        return default
    g = m.group(1)
    n = int(g) if g.isdigit() else _NUM_WORDS.get(g, default)
    return int(_clamp(n, 0, 8))


def _footprint(prompt: str) -> tuple[float, float]:
    """Best-effort house footprint (meters) from the brief."""
    m = _SIZE_RE.search(prompt or "")
    if m:
        return _clamp(_to_float(m.group(1)), 4, 16), _clamp(_to_float(m.group(2)), 4, 20)
    nums = [_to_float(x) for x in _M_RE.findall(prompt or "")]
    nums = [n for n in nums if n >= 4]  # ignore "2 baños" style noise
    if len(nums) >= 2:
        return _clamp(nums[0], 4, 16), _clamp(nums[1], 4, 20)
    a = _AREA_RE.search(prompt or "")
    if a:
        area = _clamp(float(a.group(1)), 40, 400)
        w = round(_clamp((area / 1.4) ** 0.5, 6, 14), 1)
        return w, round(_clamp(area / w, 6, 20), 1)
    return 10.0, 12.0


def rectangular_room_scene(width: float, length: float) -> dict:
    """A single rectangular room (kept for the aws-provider fallback)."""
    return house_scene(width, length, bedrooms=0, bathrooms=0, single=True)


def house_scene(width: float, length: float, *, bedrooms: int = 3,
                bathrooms: int = 2, single: bool = False) -> dict:
    h = settings.WALL_HEIGHT_M
    t = settings.DEFAULT_WALL_THICKNESS_M
    W, L = float(width), float(length)
    walls: list[dict] = []
    doors: list[dict] = []
    windows: list[dict] = []
    c = {"w": 0, "d": 0, "win": 0}

    def wall(ax, ay, bx, by):
        if abs(ax - bx) < 0.05 and abs(ay - by) < 0.05:
            return
        c["w"] += 1
        walls.append({"id": f"w{c['w']}", "start": {"x": round(ax, 2), "y": round(ay, 2)},
                      "end": {"x": round(bx, 2), "y": round(by, 2)},
                      "thickness": t, "height": h, "confidence": 1.0})

    def door(x, y):
        c["d"] += 1
        doors.append({"id": f"d{c['d']}", "wall_id": None,
                      "position": {"x": round(x, 2), "y": round(y, 2)},
                      "width": 0.9, "height": 2.1, "confidence": 1.0})

    def window(x, y, w=1.2):
        c["win"] += 1
        windows.append({"id": f"win{c['win']}", "wall_id": None,
                        "position": {"x": round(x, 2), "y": round(y, 2)},
                        "width": w, "height": 1.1, "sill_height": 0.9, "confidence": 1.0})

    def hgap(y, x0, x1, gx, gap=1.0):  # horizontal wall with a doorway gap at gx
        if gx is None or gx - gap / 2 <= x0 or gx + gap / 2 >= x1:
            wall(x0, y, x1, y)
            return
        wall(x0, y, gx - gap / 2, y)
        wall(gx + gap / 2, y, x1, y)
        door(gx, y)

    def vgap(x, y0, y1, gy, gap=1.0):  # vertical wall with a doorway gap at gy
        if gy is None or gy - gap / 2 <= y0 or gy + gap / 2 >= y1:
            wall(x, y0, x, y1)
            return
        wall(x, y0, x, gy - gap / 2)
        wall(x, gy + gap / 2, x, y1)
        door(x, gy)

    # Outer shell with a front entrance gap.
    entrance = round(W * 0.5, 2)
    hgap(0.0, 0.0, W, entrance, gap=1.0)        # front wall + entrance door
    wall(W, 0, W, L)
    wall(0, L, W, L)                             # back wall (solid; windows as markers)
    wall(0, 0, 0, L)

    if single or (bedrooms + bathrooms) <= 0:
        window(round(W * 0.5, 2), L)
        window(0.0, round(L * 0.5, 2))
        return _scene(W, L, h, t, walls, doors, windows, model="mock-design")

    # Public (front) / private (back) split with a corridor doorway.
    split = round(L * 0.58, 2)
    corridor = round(W * 0.5, 2)
    hgap(split, 0.0, W, corridor, gap=1.1)

    # Back zone: bedrooms + bathrooms as cells separated by partitions, each with
    # a doorway near the split and an exterior window on the back wall.
    nrooms = max(2, bedrooms + bathrooms)
    door_into = round(split + (L - split) * 0.22, 2)
    for i in range(1, nrooms):
        x = round(W * i / nrooms, 2)
        vgap(x, split, L, door_into, gap=0.95)
    for i in range(nrooms):
        cx = round(W * (i + 0.5) / nrooms, 2)
        window(cx, L, w=1.2)

    # Front zone: a partial partition to carve the kitchen from the living/dining.
    kx = round(W * 0.66, 2)
    wall(kx, 0.0, kx, round(split * 0.5, 2))

    # Perimeter windows (front + sides).
    window(round(W * 0.22, 2), 0.0)
    window(0.0, round(L * 0.28, 2))
    window(W, round(L * 0.28, 2))
    window(0.0, round(split + (L - split) * 0.5, 2))
    window(W, round(split + (L - split) * 0.5, 2))

    return _scene(W, L, h, t, walls, doors, windows, model="mock-design")


def _scene(W, L, h, t, walls, doors, windows, *, model):
    return {
        "image": {"width": int(W * 100), "height": int(L * 100),
                  "unit": "meters", "pixels_per_meter": None},
        "scale": {"wall_height": h, "default_wall_thickness": t},
        "walls": walls, "doors": doors, "windows": windows,
        "bounds": {"min_x": 0.0, "min_y": 0.0, "max_x": W, "max_y": L},
        "meta": {"model": model, "version": "2.0"},
    }


class MockDesignProvider(DesignProviderBase):
    name = "mock"

    def generate_scene(self, prompt: str) -> dict:
        width, length = _footprint(prompt or "")
        bedrooms = _count(prompt, "dormitor|habitac|cuarto|recamar", 3)
        bathrooms = _count(prompt, "ba[nñ]o", 2)
        return house_scene(width, length, bedrooms=bedrooms, bathrooms=bathrooms)

    def chat(self, messages: list[dict]) -> str:
        last = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        return (
            "Asistente de diseño (demo): genero una planta con distribución "
            f"(dormitorios, baños, cocina) a partir de tu descripción. Entendí: «{last[:160]}». "
            "Indica medidas y nº de ambientes y usa /api/ai-design/text para el modelo 3D."
        )
