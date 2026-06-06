"""AWS Bedrock (Claude) risk analyzer (opt-in via RISK_ANALYZER=aws).

Mirrors the Gemini analyzer but calls Bedrock through the EC2 instance role
(no keys). Reuses the same prompt and JSON extraction; degrades gracefully to
the deterministic analyzer on malformed output.
"""

from __future__ import annotations

import json

from core.aws_ai import bedrock_generate_text

from .base import RiskAnalyzerBase
from .gemini import _PROMPT, _extract_json
from .mock import MockRiskAnalyzer


class AwsRiskAnalyzer(RiskAnalyzerBase):
    name = "aws"

    def analyze(self, scene_json: dict) -> dict:
        text = bedrock_generate_text(_PROMPT + json.dumps(scene_json or {}))
        try:
            data = _extract_json(text)
            data.setdefault("findings", [])
            data.setdefault("summary", "")
            return data
        except (ValueError, json.JSONDecodeError):
            return MockRiskAnalyzer().analyze(scene_json)
