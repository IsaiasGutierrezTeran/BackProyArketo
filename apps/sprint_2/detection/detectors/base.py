"""Detector interface. Implementations return a normalized *scene* dict.

Scene schema (the contract shared with the GLB builder and the 3D editor),
mirroring the floorplan-api response::

    {
      "image":  {"width", "height", "unit", "pixels_per_meter"},
      "scale":  {"wall_height", "default_wall_thickness"},
      "walls":  [{"id", "start": {x, y}, "end": {x, y}, "thickness", "height", "confidence"}],
      "doors":  [{"id", "wall_id", "position": {x, y}, "width", "height", "confidence"}],
      "windows":[{"id", "wall_id", "position": {x, y}, "width", "height", "sill_height", "confidence"}],
      "bounds": {"min_x", "min_y", "max_x", "max_y"},
      "meta":   {"model", "version", ...}
    }
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class DetectorBase(ABC):
    """Turns a 2D plan image into a normalized scene dict."""

    name: str = "base"

    @abstractmethod
    def detect(self, image_bytes: bytes, *, options: dict | None = None) -> dict:
        """Run detection and return the normalized scene (see module docstring)."""
        raise NotImplementedError
