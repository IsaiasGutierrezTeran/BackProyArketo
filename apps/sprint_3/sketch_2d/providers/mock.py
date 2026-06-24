"""Proveedor mock: dibuja un boceto 2D simple desde el prompt (sin clave de IA).

Interpreta dimensiones aproximadas del prompt ("8x6", "8 por 6") y dibuja una
planta rectangular con divisiones y una puerta. Permite desarrollar HU-18 offline.
"""

from __future__ import annotations

import re
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from .base import SketchProviderBase

_SIZE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:x|por|×)\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE
)
WALL = (28, 32, 40)
ROOM = (226, 238, 248)
TEXT = (44, 52, 66)


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


class MockSketchProvider(SketchProviderBase):
    name = "mock"

    def generate(self, prompt: str) -> bytes:
        m = _SIZE.search(prompt or "")
        w = float(m.group(1).replace(",", ".")) if m else 8.0
        h = float(m.group(2).replace(",", ".")) if m else 6.0
        W, H = 800, 620
        img = Image.new("RGB", (W, H), "white")
        d = ImageDraw.Draw(img)

        # Título con el prompt
        d.text((40, 24), "Boceto 2D (demo)", fill=TEXT, font=_font(26))
        d.text(
            (40, 60),
            (prompt or "").strip()[:80],
            fill=(120, 130, 145),
            font=_font(16),
        )

        # Planta rectangular escalada a la dimensión del prompt
        x0, y0, x1, y1 = 60, 120, 740, 560
        d.rectangle([x0, y0, x1, y1], fill=ROOM, outline=WALL, width=8)
        midx = x0 + int((x1 - x0) * (w / (w + h)))
        d.line([midx, y0, midx, y1], fill=WALL, width=5)
        midy = (y0 + y1) // 2
        d.line([x0, midy, midx, midy], fill=WALL, width=5)
        # Puerta (hueco) en la pared inferior
        d.rectangle(
            [(x0 + midx) // 2 - 30, y1 - 4, (x0 + midx) // 2 + 30, y1 + 4],
            fill="white",
        )

        f = _font(20)
        d.text(
            ((x0 + midx) // 2 - 30, (y0 + midy) // 2),
            "Hab. 1",
            fill=TEXT,
            font=f,
        )
        d.text(
            ((x0 + midx) // 2 - 30, (midy + y1) // 2),
            "Hab. 2",
            fill=TEXT,
            font=f,
        )
        d.text(((midx + x1) // 2 - 30, midy - 10), "Estar", fill=TEXT, font=f)
        d.text(
            (x0 + 10, y1 + 12),
            f"~ {w:g} x {h:g} m",
            fill=(120, 130, 145),
            font=_font(16),
        )

        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
