"""Gemini-backed risk analyzer (opt-in via GEMINI_API_KEY + RISK_ANALYZER=gemini)."""

from __future__ import annotations

import json
import re

from core.integrations import gemini_generate_text

from .base import RiskAnalyzerBase
from .mock import MockRiskAnalyzer

_PROMPT = (
    "Eres un ingeniero estructural. Analiza esta geometría de planta (JSON) y "
    "devuelve SOLO un JSON: "
    '{"summary": "...", "findings": [{"category","severity","description","suggestion"}]}. '
    "severity ∈ low|medium|high|critical. Responde en español. Geometría: "
)


def _extract_json(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    raw = fenced.group(1) if fenced else text
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found")
    return json.loads(raw[start : end + 1])


class GeminiRiskAnalyzer(RiskAnalyzerBase):
    name = "gemini"

    def analyze(self, scene_json: dict) -> dict:
        text = gemini_generate_text(_PROMPT + json.dumps(scene_json or {}))
        try:
            data = _extract_json(text)
            data.setdefault("findings", [])
            data.setdefault("summary", "")
            return data
        except (ValueError, json.JSONDecodeError):
            # Degrade gracefully to the deterministic analyzer rather than fail.
            return MockRiskAnalyzer().analyze(scene_json)
