"""Proveedores de generación de boceto 2D (mock por defecto)."""

from .base import SketchProviderBase
from .gemini import GeminiSketchProvider
from .mock import MockSketchProvider

__all__ = ["SketchProviderBase", "MockSketchProvider", "GeminiSketchProvider"]
