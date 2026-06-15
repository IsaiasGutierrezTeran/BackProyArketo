"""Deterministic, *program-aware* mock design provider (no API key needed).

Parses a free-text Spanish brief into a **standard single-story house program**
(dormitorios, baños, sala, comedor, cocina, lavandería, garaje 1/2 autos) and a
footprint, then lays out a realistic distribution on one floor:

* a SOCIAL zone (sala / comedor / cocina) at the front,
* a PRIVATE zone (dormitorios — the principal is the largest — + baños) at the
  back, off a circulation corridor,
* service (lavandería) and an optional garage (1 or 2 autos),

all wired together with **real doorway gaps** in the interior walls and windows
punched into the exterior walls. Every requested room is emitted *and labelled*
in the ``rooms`` array.

Output is the exact normalized ``scene_json`` contract consumed by the 3D GLB
builder (``modeling.glb.build_glb_bytes``) and the 2D plan renderer
(``modeling.plan2d``), so the mock flows end-to-end offline (CU9).

scene_json contract (this provider emits it EXACTLY):
    {
      "image":   {"unit":"meters","pixels_per_meter":null},
      "scale":   {"wall_height":2.7,"default_wall_thickness":0.12},
      "walls":   [{"id","start":{"x","y"},"end":{"x","y"},"thickness","height","confidence"}],
      "doors":   [{"id","wall_id":null,"position":{"x","y"},"width","height","confidence"}],
      "windows": [{"id","wall_id":null,"position":{"x","y"},"width","height","sill_height","confidence"}],
      "rooms":   [{"name","x","y","w","h","area"}],   # x,y = CENTER of the room
      "bounds":  {"min_x","min_y","max_x","max_y"},
      "meta":    {"model","version"}
    }

Coordinates are in METERS, plan (x, y), origin (0, 0) at the BOTTOM-LEFT.
Exterior walls are 0.20 m thick; interior walls 0.12 m.
"""

from __future__ import annotations

import re

from django.conf import settings

from .base import DesignProviderBase

# --------------------------------------------------------------------------- #
# Brief parsing (free Spanish text)
# --------------------------------------------------------------------------- #
_SIZE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:x|por|×)\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
_M_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*m(?:etros|²|2)?\b", re.IGNORECASE)
_AREA_RE = re.compile(r"(\d{2,4})\s*m(?:²|2)\b", re.IGNORECASE)
_NUM_WORDS = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4,
              "cinco": 5, "seis": 6, "siete": 7, "ocho": 8}

# Exterior / interior wall thicknesses (meters) per the contract.
_T_EXT = 0.20
_T_INT = 0.12


def _to_float(value: str) -> float:
    return float(value.replace(",", "."))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(v, hi))


_NUM_TOKEN = r"\d+|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho"


def _count(prompt: str, kw_regex: str, default: int) -> int:
    """How many of <kw> the brief asks for.

    Binds a number to the *nearest* following noun. The optional filler between
    the number and the noun may be at most one short adjective and must NOT itself
    be another number word (so "dos dormitorios y un baño" reads 2 dormitorios /
    1 baño instead of letting "dos" leak onto "baño"). When the noun appears with
    no leading count, assume 1; when it's absent entirely, use ``default``.
    """
    p = (prompt or "").lower()
    # number, then optionally a single non-number filler word, then the noun.
    pattern = (
        r"(" + _NUM_TOKEN + r")\s+"
        r"(?:(?!" + _NUM_TOKEN + r")[a-záéíóúñ]+\s+)?"
        r"(?:" + kw_regex + r")"
    )
    m = re.search(pattern, p)
    if m:
        g = m.group(1)
        n = int(g) if g.isdigit() else _NUM_WORDS.get(g, default)
        return int(_clamp(n, 0, 8))
    # The noun is present but not counted -> assume 1; absent -> default.
    if re.search(r"(?:" + kw_regex + ")", p):
        return 1
    return default


def _has(prompt: str, kw_regex: str) -> bool:
    return re.search(kw_regex, (prompt or "").lower()) is not None


def _garage_cars(prompt: str) -> int:
    """0 = no garage, 1 = single, 2 = double (parsed from the brief)."""
    p = (prompt or "").lower()
    if not _has(p, r"garaje|garage|coch(?:era|e)|estacionamiento|parqueo|coche"):
        return 0
    # Explicit "2 autos" / "doble" => double; else single.
    if re.search(r"(2|dos|doble)\s+(?:[a-záéíóúñ]+\s+){0,2}?(?:auto|carro|coche|veh[ií]culo|plaza)", p):
        return 2
    if re.search(r"garaje\s+doble|cochera\s+doble|doble\s+garaje|para\s+(?:2|dos)\b", p):
        return 2
    return 1


def _program(prompt: str) -> dict:
    """The full requested program parsed from the brief."""
    return {
        "bedrooms": _count(prompt, r"dormitor|habitac|cuarto|recamar|rec[aá]mar|alcoba", 3),
        "bathrooms": _count(prompt, r"ba[nñ]o|servicio higi[eé]nico|sshh|aseo", 2),
        "sala": _has(prompt, r"\bsala\b|living|estar|salón|salon"),
        "comedor": _has(prompt, r"comedor|comer"),
        "cocina": _has(prompt, r"cocina|kitchen"),
        "lavanderia": _has(prompt, r"lavander[ií]a|lavado|lavader"),
        "garage_cars": _garage_cars(prompt),
    }


def _footprint(prompt: str) -> tuple[float, float]:
    """Best-effort house footprint (meters) from the brief; (W, L)."""
    m = _SIZE_RE.search(prompt or "")
    if m:
        return _clamp(_to_float(m.group(1)), 6, 20), _clamp(_to_float(m.group(2)), 6, 24)
    nums = [_to_float(x) for x in _M_RE.findall(prompt or "")]
    nums = [n for n in nums if n >= 5]  # ignore "2 baños" style noise
    if len(nums) >= 2:
        return _clamp(nums[0], 6, 20), _clamp(nums[1], 6, 24)
    a = _AREA_RE.search(prompt or "")
    if a:
        area = _clamp(float(a.group(1)), 50, 400)
        w = round(_clamp((area / 1.4) ** 0.5, 7, 16), 1)
        return w, round(_clamp(area / w, 8, 24), 1)
    return 10.0, 12.0


# --------------------------------------------------------------------------- #
# Scene builder
# --------------------------------------------------------------------------- #
class _Builder:
    """Accumulates walls / doors / windows / rooms for one scene (meters)."""

    def __init__(self, wall_h: float) -> None:
        self.h = float(wall_h)
        self.walls: list[dict] = []
        self.doors: list[dict] = []
        self.windows: list[dict] = []
        self.rooms: list[dict] = []
        self._c = {"w": 0, "d": 0, "win": 0}

    # -- primitives --------------------------------------------------------- #
    def wall(self, ax, ay, bx, by, *, thickness=_T_INT):
        if abs(ax - bx) < 0.04 and abs(ay - by) < 0.04:
            return
        self._c["w"] += 1
        self.walls.append({
            "id": f"w{self._c['w']}",
            "start": {"x": round(ax, 2), "y": round(ay, 2)},
            "end": {"x": round(bx, 2), "y": round(by, 2)},
            "thickness": float(thickness), "height": self.h, "confidence": 1.0,
        })

    def door(self, x, y, *, width=0.9):
        self._c["d"] += 1
        self.doors.append({
            "id": f"d{self._c['d']}", "wall_id": None,
            "position": {"x": round(x, 2), "y": round(y, 2)},
            "width": float(width), "height": 2.1, "confidence": 1.0,
        })

    def window(self, x, y, *, width=1.2):
        self._c["win"] += 1
        self.windows.append({
            "id": f"win{self._c['win']}", "wall_id": None,
            "position": {"x": round(x, 2), "y": round(y, 2)},
            "width": float(width), "height": 1.1, "sill_height": 0.9, "confidence": 1.0,
        })

    def room(self, name, x0, y0, x1, y1):
        """Register a labelled room from its bounding box (center + dims + area)."""
        w = abs(x1 - x0)
        h = abs(y1 - y0)
        self.rooms.append({
            "name": str(name),
            "x": round((x0 + x1) / 2.0, 2), "y": round((y0 + y1) / 2.0, 2),
            "w": round(w, 2), "h": round(h, 2), "area": round(w * h, 2),
        })

    # -- composite walls with openings ------------------------------------- #
    def hgap(self, y, x0, x1, gx, *, gap=0.95, thickness=_T_INT, leaf=0.9):
        """Horizontal interior wall from x0..x1 at height y, with a doorway at gx."""
        if gx is None or gx - gap / 2 <= x0 + 0.05 or gx + gap / 2 >= x1 - 0.05:
            self.wall(x0, y, x1, y, thickness=thickness)
            return
        self.wall(x0, y, gx - gap / 2, y, thickness=thickness)
        self.wall(gx + gap / 2, y, x1, y, thickness=thickness)
        self.door(gx, y, width=leaf)

    def vgap(self, x, y0, y1, gy, *, gap=0.95, thickness=_T_INT, leaf=0.9):
        """Vertical interior wall from y0..y1 at x, with a doorway at gy."""
        if gy is None or gy - gap / 2 <= y0 + 0.05 or gy + gap / 2 >= y1 - 0.05:
            self.wall(x, y0, x, y1, thickness=thickness)
            return
        self.wall(x, y0, x, gy - gap / 2, thickness=thickness)
        self.wall(x, gy + gap / 2, x, y1, thickness=thickness)
        self.door(x, gy, width=leaf)

    def scene(self, W, L, t, *, model="mock-design"):
        return {
            "image": {"unit": "meters", "pixels_per_meter": None},
            "scale": {"wall_height": self.h, "default_wall_thickness": t},
            "walls": self.walls, "doors": self.doors, "windows": self.windows,
            "rooms": self.rooms,
            "bounds": {"min_x": 0.0, "min_y": 0.0,
                       "max_x": round(W, 2), "max_y": round(L, 2)},
            "meta": {"model": model, "version": "3.0"},
        }


# --------------------------------------------------------------------------- #
# Single rectangular room (fallback for aws / gemini providers)
# --------------------------------------------------------------------------- #
def rectangular_room_scene(width: float, length: float) -> dict:
    """A single labelled rectangular room (kept for the aws/gemini fallback)."""
    h = settings.WALL_HEIGHT_M
    W, L = float(width), float(length)
    b = _Builder(h)
    # Outer shell with a front entrance.
    entrance = round(W * 0.5, 2)
    b.hgap(0.0, 0.0, W, entrance, gap=1.0, thickness=_T_EXT, leaf=0.9)  # front + door
    b.wall(W, 0, W, L, thickness=_T_EXT)
    b.wall(0, L, W, L, thickness=_T_EXT)
    b.wall(0, 0, 0, L, thickness=_T_EXT)
    # A couple of windows so it never reads as a blind box.
    b.window(round(W * 0.5, 2), L)
    b.window(0.0, round(L * 0.5, 2))
    b.window(W, round(L * 0.5, 2))
    b.room("Ambiente", 0.0, 0.0, W, L)
    return b.scene(W, L, _T_INT, model="mock-design")


# --------------------------------------------------------------------------- #
# Program-aware single-story house
# --------------------------------------------------------------------------- #
def house_scene(width: float, length: float, *, bedrooms: int = 3,
                bathrooms: int = 2, single: bool = False,
                program: dict | None = None) -> dict:
    """Lay out a realistic single-story house honoring the requested program.

    ``program`` (when given) drives which ambientes appear (sala/comedor/cocina/
    lavandería/garaje). When omitted, a sensible default program is assumed so
    the function stays backward compatible with positional bedroom/bathroom use.
    """
    h = settings.WALL_HEIGHT_M
    W, L = float(width), float(length)

    if program is None:
        program = {
            "bedrooms": bedrooms, "bathrooms": bathrooms,
            "sala": True, "comedor": True, "cocina": True,
            "lavanderia": True, "garage_cars": 0,
        }
    bedrooms = int(program.get("bedrooms", bedrooms))
    bathrooms = int(program.get("bathrooms", bathrooms))

    b = _Builder(h)

    # Degenerate program -> single open ambiente.
    if single or (bedrooms + bathrooms
                  + sum(1 for k in ("sala", "comedor", "cocina", "lavanderia")
                        if program.get(k))) <= 0:
        return rectangular_room_scene(W, L)

    # ---- Optional garage carved off the RIGHT side of the lot ------------- #
    # The garage spans the full depth on the right. Its width is capped so it
    # never starves the conditioned house: we keep at least ``min_house`` meters
    # (and >= 55% of W) for the rooms, shrinking the garage to fit when needed.
    cars = int(program.get("garage_cars", 0))
    garage_w = 0.0
    if cars >= 1:
        want = (3.2 if cars == 1 else 5.6)       # nominal single / double bay
        min_house = max(W * 0.55, 5.5)
        garage_w = round(_clamp(want, 2.6, max(0.0, W - min_house)), 2)
        if garage_w < 2.6:                       # footprint too small for a bay
            garage_w = 0.0
            cars = 0
    house_w = round(W - garage_w, 2)            # the conditioned house (left block)
    gx0 = house_w                               # garage spans gx0..W

    # ---- Outer shell of the WHOLE footprint (exterior walls, t = 0.20) ---- #
    entrance = round(house_w * 0.5, 2)          # front door into the house block
    # Front wall: split so the house gets a real entrance doorway; the garage
    # front becomes a vehicle opening (wide) when present.
    b.hgap(0.0, 0.0, house_w, entrance, gap=1.0, thickness=_T_EXT, leaf=0.95)
    if garage_w > 0:
        gdoor = round(gx0 + garage_w / 2.0, 2)
        gwidth = round(_clamp(garage_w * 0.78, 2.3, 5.0), 2)
        b.hgap(0.0, gx0, W, gdoor, gap=gwidth + 0.02, thickness=_T_EXT, leaf=gwidth)
    b.wall(W, 0, W, L, thickness=_T_EXT)        # right exterior
    b.wall(0, L, W, L, thickness=_T_EXT)        # back exterior
    b.wall(0, 0, 0, L, thickness=_T_EXT)        # left exterior

    # ---- Garage interior --------------------------------------------------- #
    if garage_w > 0:
        # Partition between garage and house, with an interior service door.
        b.vgap(gx0, 0.0, L, round(L * 0.30, 2), gap=0.95, thickness=_T_INT, leaf=0.9)
        b.window(W, round(L * 0.6, 2))          # garage side window
        b.room("Garaje", gx0, 0.0, W, L)

    # ====================================================================== #
    # House block: 0..house_w in X, 0..L in Y.
    # SOCIAL zone at the front (low Y), PRIVATE zone at the back (high Y),
    # joined by a corridor doorway in the dividing wall.
    # ====================================================================== #
    split = round(L * 0.55, 2)                   # social/private divider (Y)
    corridor = round(house_w * 0.5, 2)           # corridor crosses at this X
    b.hgap(split, 0.0, house_w, corridor, gap=1.1, thickness=_T_INT, leaf=1.0)

    # ---- PRIVATE zone (back): bedrooms (principal largest) + bathrooms ----- #
    nbed = max(1, bedrooms)
    nbath = max(0, bathrooms)
    # Lay private cells side by side across X. Principal bedroom gets ~1.5x width.
    # Order: [principal][bedroom...][bath...]
    weights: list[tuple[str, float]] = []
    weights.append(("Dormitorio principal", 1.5))
    for i in range(2, nbed + 1):
        weights.append((f"Dormitorio {i}", 1.0))
    for i in range(1, nbath + 1):
        weights.append((f"Baño {i}" if nbath > 1 else "Baño", 0.62))
    total_w = sum(w for _, w in weights)

    # Doorway target: near the corridor side of each private cell.
    door_y = round(split + (L - split) * 0.18, 2)
    x_cursor = 0.0
    n_cells = len(weights)
    for idx, (name, wgt) in enumerate(weights):
        cell_w = (house_w * wgt / total_w) if total_w > 0 else house_w
        x0 = x_cursor
        x1 = round(min(x_cursor + cell_w, house_w), 2)
        # Interior partition between this cell and the next (vertical wall).
        if idx < n_cells - 1:
            b.vgap(x1, split, L, door_y, gap=0.9,
                   thickness=_T_INT, leaf=0.8 if name.startswith("Baño") else 0.85)
        # Exterior window on the back wall for habitable rooms (not tiny baths).
        cx = round((x0 + x1) / 2.0, 2)
        if not name.startswith("Baño"):
            b.window(cx, L, width=round(_clamp((x1 - x0) * 0.5, 0.9, 1.6), 2))
        b.room(name, x0, split, x1, L)
        x_cursor = x1

    # ---- SOCIAL zone (front): sala / comedor / cocina + lavandería -------- #
    want_sala = bool(program.get("sala"))
    want_comedor = bool(program.get("comedor"))
    want_cocina = bool(program.get("cocina"))
    want_lavanderia = bool(program.get("lavanderia"))

    # The social band 0..split (Y) is split into columns. Kitchen + laundry are
    # service spaces grouped to the RIGHT (near the corridor / back-of-house);
    # sala + comedor are the open public area to the LEFT.
    social_cells: list[tuple[str, float]] = []
    if want_sala:
        social_cells.append(("Sala", 1.4))
    if want_comedor:
        social_cells.append(("Comedor", 1.1))
    if want_cocina:
        social_cells.append(("Cocina", 1.0))
    if not social_cells:
        # Always give the house *some* social room so the front isn't empty.
        social_cells.append(("Sala", 1.0))

    # Laundry is a small service cell carved at the front-right corner when asked.
    laundry_w = 0.0
    if want_lavanderia:
        laundry_w = round(_clamp(house_w * 0.18, 1.6, 2.6), 2)

    social_w = round(house_w - laundry_w, 2)
    total_s = sum(w for _, w in social_cells)
    x_cursor = 0.0
    door_into_social = round(split * 0.5, 2)     # doorway height for social partitions
    n_soc = len(social_cells)
    for idx, (name, wgt) in enumerate(social_cells):
        cw = (social_w * wgt / total_s) if total_s > 0 else social_w
        x0 = x_cursor
        x1 = round(min(x_cursor + cw, social_w), 2)
        last_social = idx == n_soc - 1
        # Partition to the next social cell. Sala<->Comedor is an OPEN connection
        # (a wide vano) and Cocina is more enclosed (door).
        if not last_social or laundry_w > 0:
            cur_kitchen = name == "Cocina"
            nxt = social_cells[idx + 1][0] if not last_social else "Lavandería"
            nxt_kitchen = nxt in ("Cocina", "Lavandería")
            if cur_kitchen or nxt_kitchen:
                b.vgap(x1, 0.0, split, door_into_social, gap=1.0,
                       thickness=_T_INT, leaf=0.9)
            else:
                # Open living/dining: a wide pass-through vano (no leaf swing).
                b.vgap(x1, 0.0, split, round(split * 0.5, 2), gap=1.6,
                       thickness=_T_INT, leaf=1.5)
        cx = round((x0 + x1) / 2.0, 2)
        # Front windows for habitable social rooms (skip the tight kitchen sill
        # only if it would overlap the entrance door).
        if abs(cx - entrance) > 1.0:
            b.window(cx, 0.0, width=round(_clamp((x1 - x0) * 0.45, 0.9, 1.8), 2))
        b.room(name, x0, 0.0, x1, split)
        x_cursor = x1

    if laundry_w > 0:
        lx0 = social_w
        lx1 = house_w
        # Door from the adjacent social cell (likely kitchen) into the laundry.
        b.vgap(lx0, 0.0, split, round(split * 0.45, 2), gap=0.85,
               thickness=_T_INT, leaf=0.8)
        b.window(round((lx0 + lx1) / 2.0, 2), 0.0, width=0.9)
        b.room("Lavandería", lx0, 0.0, lx1, split)

    # ---- Perimeter side windows for the house block (left/right exterior) -- #
    b.window(0.0, round(L * 0.28, 2))            # left, social side
    b.window(0.0, round(split + (L - split) * 0.5, 2))  # left, private side
    if garage_w <= 0:                            # right is exterior only w/o garage
        b.window(house_w, round(L * 0.28, 2))
        b.window(house_w, round(split + (L - split) * 0.5, 2))

    return b.scene(W, L, _T_INT, model="mock-design")


# --------------------------------------------------------------------------- #
# Provider
# --------------------------------------------------------------------------- #
class MockDesignProvider(DesignProviderBase):
    name = "mock"

    def generate_scene(self, prompt: str) -> dict:
        width, length = _footprint(prompt or "")
        prog = _program(prompt or "")
        return house_scene(width, length,
                           bedrooms=prog["bedrooms"], bathrooms=prog["bathrooms"],
                           program=prog)

    def chat(self, messages: list[dict]) -> str:
        last = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        return (
            "Asistente de diseño (demo): genero una planta de una sola altura con "
            "zona social (sala/comedor/cocina), zona privada (dormitorios con el "
            "principal más grande + baños), lavandería y garaje según tu "
            f"descripción. Entendí: «{last[:160]}». Indica medidas (AxB o m²) y nº "
            "de ambientes y usa /api/ai-design/text para el modelo 3D."
        )
