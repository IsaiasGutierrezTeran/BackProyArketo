"""Risk analyzer interface.

`analyze` returns ``{"summary": str, "findings": [{"category", "severity",
"description", "suggestion"}]}`` where severity is one of low|medium|high|critical.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class RiskAnalyzerBase(ABC):
    name: str = "base"

    @abstractmethod
    def analyze(self, scene_json: dict) -> dict:
        raise NotImplementedError
