"""Gemini-backed design provider (opt-in via GEMINI_API_KEY + provider=gemini)."""

from __future__ import annotations

import json
import re

from core.exceptions import ApiException
from core.integrations import gemini_generate_text

from .base import DesignProviderBase
from .mock import rectangular_room_scene

_SCENE_PROMPT = (
    "Eres un asistente de arquitectura. A partir de la descripción del usuario, "
    "devuelve SOLO un JSON con esta forma: "
    '{"walls":[{"id","start":{"x","y"},"end":{"x","y"},"thickness","height"}],'
    '"doors":[{"id","wall_id","position":{"x","y"},"width","height"}],'
    '"windows":[{"id","wall_id","position":{"x","y"},"width","height","sill_height"}]}. '
    "Coordenadas en metros, planta (x,y). Sin texto adicional. Descripción: "
)


def _extract_json(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    raw = fenced.group(1) if fenced else text
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found")
    return json.loads(raw[start : end + 1])


class GeminiDesignProvider(DesignProviderBase):
    name = "gemini"

    def generate_scene(self, prompt: str) -> dict:
        text = gemini_generate_text(_SCENE_PROMPT + (prompt or ""))
        try:
            scene = _extract_json(text)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ApiException(
                "La IA no devolvió un plano válido. Reintenta con más detalle.",
                code="inference_error", status_code=502,
            ) from exc
        # Ensure the minimum required structure for the GLB builder.
        scene.setdefault("walls", [])
        scene.setdefault("doors", [])
        scene.setdefault("windows", [])
        if not scene["walls"]:
            scene = rectangular_room_scene(5.0, 4.0)
        scene.setdefault("meta", {"model": "gemini-design", "version": "1.0"})
        scene.setdefault("image", {"unit": "meters", "pixels_per_meter": None})
        return scene

    def chat(self, messages: list[dict]) -> str:
        convo = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in messages)
        return gemini_generate_text(
            "Eres un asistente de diseño arquitectónico. Responde en español, "
            "conciso y útil.\n" + convo
        )
