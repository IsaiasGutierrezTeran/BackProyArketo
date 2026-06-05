"""Design provider interface.

`generate_scene` returns the same normalized scene schema used by detection and
the GLB builder, so AI-designed plans flow through the exact same 3D pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class DesignProviderBase(ABC):
    name: str = "base"

    @abstractmethod
    def generate_scene(self, prompt: str) -> dict:
        """Turn a natural-language brief into a normalized scene dict."""
        raise NotImplementedError

    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        """Return the assistant reply for a conversation (list of {role, content})."""
        raise NotImplementedError
