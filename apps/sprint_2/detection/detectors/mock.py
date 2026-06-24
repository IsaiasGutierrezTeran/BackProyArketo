"""Deterministic mock detector — a 5x4 m room with one door and one window.

Lets the whole 2D->3D pipeline run without GPU, weights or the legacy service.
"""

from __future__ import annotations

from django.conf import settings

from .base import DetectorBase


class MockDetector(DetectorBase):
    name = "mock"

    def detect(
        self, image_bytes: bytes, *, options: dict | None = None
    ) -> dict:
        h = settings.WALL_HEIGHT_M
        t = settings.DEFAULT_WALL_THICKNESS_M
        return {
            "image": {
                "width": 500,
                "height": 400,
                "unit": "meters",
                "pixels_per_meter": None,
            },
            "scale": {"wall_height": h, "default_wall_thickness": t},
            "walls": [
                {
                    "id": "w1",
                    "start": {"x": 0.0, "y": 0.0},
                    "end": {"x": 5.0, "y": 0.0},
                    "thickness": t,
                    "height": h,
                    "confidence": 0.99,
                },
                {
                    "id": "w2",
                    "start": {"x": 5.0, "y": 0.0},
                    "end": {"x": 5.0, "y": 4.0},
                    "thickness": t,
                    "height": h,
                    "confidence": 0.99,
                },
                {
                    "id": "w3",
                    "start": {"x": 5.0, "y": 4.0},
                    "end": {"x": 0.0, "y": 4.0},
                    "thickness": t,
                    "height": h,
                    "confidence": 0.99,
                },
                {
                    "id": "w4",
                    "start": {"x": 0.0, "y": 4.0},
                    "end": {"x": 0.0, "y": 0.0},
                    "thickness": t,
                    "height": h,
                    "confidence": 0.99,
                },
            ],
            "doors": [
                {
                    "id": "d1",
                    "wall_id": "w1",
                    "position": {"x": 2.5, "y": 0.0},
                    "width": 0.9,
                    "height": 2.1,
                    "confidence": 0.95,
                },
            ],
            "windows": [
                {
                    "id": "win1",
                    "wall_id": "w2",
                    "position": {"x": 5.0, "y": 2.0},
                    "width": 1.2,
                    "height": 1.1,
                    "sill_height": 0.9,
                    "confidence": 0.95,
                },
            ],
            "bounds": {"min_x": 0.0, "min_y": 0.0, "max_x": 5.0, "max_y": 4.0},
            "meta": {"model": "mock", "version": "1.0"},
        }
