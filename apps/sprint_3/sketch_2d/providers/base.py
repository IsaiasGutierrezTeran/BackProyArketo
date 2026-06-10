"""Interfaz de proveedor de boceto 2D. `generate` devuelve bytes PNG."""

from __future__ import annotations

from abc import ABC, abstractmethod


class SketchProviderBase(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, prompt: str) -> bytes:
        """Genera una imagen 2D (PNG en bytes) a partir del prompt."""
        raise NotImplementedError
