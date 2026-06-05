"""AWS Bedrock (Claude) design provider (opt-in via AI_DESIGN_PROVIDER=aws).

Mirrors the Gemini provider but calls Bedrock through the EC2 instance role
(no keys). Reuses the same scene prompt and JSON extraction so AI-designed plans
flow through the exact same 3D pipeline.
"""

from __future__ import annotations

import json

from core.aws_ai import bedrock_generate_text
from core.exceptions import ApiException

from .base import DesignProviderBase
from .gemini import _SCENE_PROMPT, _extract_json
from .mock import rectangular_room_scene


class AwsDesignProvider(DesignProviderBase):
    name = "aws"

    def generate_scene(self, prompt: str) -> dict:
        text = bedrock_generate_text(_SCENE_PROMPT + (prompt or ""), max_tokens=2000)
        try:
            scene = _extract_json(text)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ApiException(
                "La IA no devolvió un plano válido. Reintenta con más detalle.",
                code="inference_error", status_code=502,
            ) from exc
        scene.setdefault("walls", [])
        scene.setdefault("doors", [])
        scene.setdefault("windows", [])
        if not scene["walls"]:
            scene = rectangular_room_scene(5.0, 4.0)
        scene.setdefault("meta", {"model": "bedrock-design", "version": "1.0"})
        scene.setdefault("image", {"unit": "meters", "pixels_per_meter": None})
        return scene

    def chat(self, messages: list[dict]) -> str:
        convo = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in messages)
        return bedrock_generate_text(
            convo,
            system=(
                "Eres un asistente de diseño arquitectónico. Responde en español, "
                "conciso y útil."
            ),
        )
