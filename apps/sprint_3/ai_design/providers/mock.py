"""Deterministic mock design provider (no API key needed).

Parses an approximate room size ("6x4", "6 por 4") from the brief and returns a
rectangular room scene with one door. Lets CU9 work end-to-end offline.
"""

from __future__ import annotations

import re

from django.conf import settings

from .base import DesignProviderBase

_SIZE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:x|por|×)\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)


def _to_float(value: str) -> float:
    return float(value.replace(",", "."))


def rectangular_room_scene(width: float, length: float) -> dict:
    h = settings.WALL_HEIGHT_M
    t = settings.DEFAULT_WALL_THICKNESS_M

    def wall(wid, a, b):
        return {"id": wid, "start": {"x": a[0], "y": a[1]}, "end": {"x": b[0], "y": b[1]},
                "thickness": t, "height": h, "confidence": 1.0}

    return {
        "image": {"width": int(width * 100), "height": int(length * 100),
                  "unit": "meters", "pixels_per_meter": None},
        "scale": {"wall_height": h, "default_wall_thickness": t},
        "walls": [
            wall("w1", (0, 0), (width, 0)),
            wall("w2", (width, 0), (width, length)),
            wall("w3", (width, length), (0, length)),
            wall("w4", (0, length), (0, 0)),
        ],
        "doors": [
            {"id": "d1", "wall_id": "w1", "position": {"x": round(width / 2, 2), "y": 0.0},
             "width": 0.9, "height": 2.1, "confidence": 1.0},
        ],
        "windows": [],
        "bounds": {"min_x": 0.0, "min_y": 0.0, "max_x": width, "max_y": length},
        "meta": {"model": "mock-design", "version": "1.0"},
    }


class MockDesignProvider(DesignProviderBase):
    name = "mock"

    def generate_scene(self, prompt: str) -> dict:
        match = _SIZE_RE.search(prompt or "")
        width = _to_float(match.group(1)) if match else 5.0
        length = _to_float(match.group(2)) if match else 4.0
        # Clamp to sane bounds.
        width = max(2.0, min(width, 50.0))
        length = max(2.0, min(length, 50.0))
        return rectangular_room_scene(width, length)

    def chat(self, messages: list[dict]) -> str:
        last = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        return (
            "Asistente de diseño (demo): puedo generar un plano a partir de tu "
            f"descripción. Entendí: «{last[:160]}». Indícame dimensiones (p. ej. "
            "«6 x 4 metros») y usa /api/ai-design/text para generar el modelo 3D."
        )
