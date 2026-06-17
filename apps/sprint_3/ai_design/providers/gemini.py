"""Gemini-backed design provider (opt-in via GEMINI_API_KEY + provider=gemini)."""

from __future__ import annotations

import json
import re

from core.exceptions import ApiException
from core.integrations import gemini_generate_text

from .base import DesignProviderBase

_SCENE_PROMPT = (
    "Eres un arquitecto. A partir de la descripción del usuario, diseña una planta "
    "arquitectónica realista de una vivienda y devuelve SOLO un objeto JSON (sin "
    "texto adicional, sin markdown) que cumpla EXACTAMENTE este contrato:\n"
    '{'
    '"image":{"unit":"meters","pixels_per_meter":null},'
    '"scale":{"wall_height":2.7,"default_wall_thickness":0.12},'
    '"walls":[{"id":"w1","start":{"x":0,"y":0},"end":{"x":8,"y":0},"thickness":0.20,"height":2.7}],'
    '"doors":[{"id":"d1","wall_id":"w1","position":{"x":4,"y":0},"width":0.9,"height":2.1}],'
    '"windows":[{"id":"v1","wall_id":"w1","position":{"x":2,"y":0},"width":1.2,"height":1.2,"sill_height":1.0}],'
    '"rooms":[{"name":"Sala","x":2,"y":2,"w":4,"h":4,"area":16}],'
    '"bounds":{"min_x":0,"min_y":0,"max_x":8,"max_y":6}'
    '}\n'
    "REGLAS OBLIGATORIAS:\n"
    "- Coordenadas en METROS, planta (x,y), origen (0,0) abajo-izquierda.\n"
    "- Muros EXTERIORES thickness 0.20, muros INTERIORES 0.12; height 2.7.\n"
    "- Cada puerta/ventana DEBE referenciar el wall_id del muro que la contiene y "
    "su position debe estar sobre ese muro.\n"
    "- 'rooms' DEBE incluir TODOS los ambientes pedidos (sala, comedor, cocina, "
    "dormitorios, baños, lavandería, garaje…) con name en español, x,y = CENTRO "
    "del ambiente, w,h en metros y area = w*h aproximada.\n"
    "- Distribuye con sentido: zona social al frente, dormitorios y baños en zona "
    "privada, circulación entre ambientes. Respeta las medidas/ambientes pedidos.\n"
    "- 'bounds' debe envolver toda la planta.\n"
    "Descripción del usuario: "
)


def _normalize_scene(scene: dict, *, model: str, prompt: str) -> dict:
    """Garantiza el contrato mínimo; si el LLM no da muros, cae a una planta
    procedural *program-aware* (no a una caja genérica) marcando meta.fallback."""
    scene.setdefault("walls", [])
    scene.setdefault("doors", [])
    scene.setdefault("windows", [])
    if not scene["walls"]:
        # Fallback útil: reusa el generador procedural que SÍ interpreta el
        # programa (nº ambientes, medidas) en vez de un cuarto 5x4 sin sentido.
        from .mock import MockDesignProvider

        scene = MockDesignProvider().generate_scene(prompt)
        scene.setdefault("meta", {})
        scene["meta"]["fallback"] = True
        scene["meta"]["intended_model"] = model
        return scene
    scene.setdefault("rooms", [])
    scene.setdefault("scale", {"wall_height": 2.7, "default_wall_thickness": 0.12})
    scene.setdefault("meta", {"model": model, "version": "1.0"})
    scene.setdefault("image", {"unit": "meters", "pixels_per_meter": None})
    return scene


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
        return _normalize_scene(scene, model="gemini-design", prompt=prompt or "")

    def chat(self, messages: list[dict]) -> str:
        convo = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in messages)
        return gemini_generate_text(
            "Eres un asistente de diseño arquitectónico. Responde en español, "
            "conciso y útil.\n" + convo
        )
