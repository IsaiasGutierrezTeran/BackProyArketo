"""Vision-LLM detector: a multimodal model *reads* the plan image directly.

Handles the plans the legacy Mask R-CNN can't — colored / rendered / furnished
floor plans (e.g. Floorplanner exports) — and uses the written dimensions
(cotas) on the drawing to set a real-world scale in meters. Returns the same
normalized scene contract as the other detectors (see ``base``), so it flows
through the exact same GLB + 2D pipeline.

Opt-in: ``DETECTION_DEFAULT_DETECTOR=gemini-vision`` (+ ``GEMINI_API_KEY``).
"""

from __future__ import annotations

import json

from core.exceptions import ApiException

from .base import DetectorBase

_VISION_PROMPT = (
    "Eres un arquitecto experto en leer planos. Analiza ESTA IMAGEN de un plano "
    "arquitectónico (puede estar a color, con muebles, texturas y cotas escritas) "
    "y devuelve SOLO un objeto JSON (sin texto adicional, sin markdown) con este "
    "contrato EXACTO:\n"
    '{'
    '"image":{"unit":"meters","pixels_per_meter":null},'
    '"scale":{"wall_height":2.7,"default_wall_thickness":0.12},'
    '"walls":[{"id":"w1","start":{"x":0,"y":0},"end":{"x":8,"y":0},"thickness":0.20,"height":2.7,"confidence":0.9}],'
    '"doors":[{"id":"d1","wall_id":"w1","position":{"x":4,"y":0},"width":0.9,"height":2.1,"confidence":0.9}],'
    '"windows":[{"id":"win1","wall_id":"w1","position":{"x":2,"y":0},"width":1.2,"height":1.2,"sill_height":1.0,"confidence":0.9}],'
    '"rooms":[{"name":"Sala","x":2,"y":2,"w":4,"h":4,"area":16}],'
    '"bounds":{"min_x":0,"min_y":0,"max_x":8,"max_y":6}'
    '}\n'
    "REGLAS OBLIGATORIAS:\n"
    "- USA LAS COTAS/MEDIDAS escritas en el plano (p. ej. '8.61 m', '13.61 m', "
    "áreas en m²) para fijar la ESCALA REAL en METROS. Si no hay cotas, estima "
    "proporciones razonables para una vivienda.\n"
    "- Coordenadas en METROS, planta (x,y), origen (0,0) abajo-izquierda.\n"
    "- Traza TODOS los muros como segmentos (exteriores ~0.20 m, interiores "
    "~0.12 m de grosor). Ignora muebles, sombras y texturas: son decoración, NO "
    "muros.\n"
    "- Cada puerta/ventana referencia el wall_id del muro que la contiene y su "
    "position cae sobre ese muro.\n"
    "- 'rooms' incluye TODOS los ambientes visibles con su nombre real (lee las "
    "etiquetas del plano: dormitorio, sala, cocina, baño, garaje, etc.), x,y = "
    "CENTRO del ambiente, w,h en metros y area aproximada.\n"
    "- 'bounds' envuelve toda la planta.\n"
)


def _sniff_mime(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


class VisionLLMDetector(DetectorBase):
    name = "gemini-vision"

    def detect(self, image_bytes: bytes, *, options: dict | None = None) -> dict:
        # Lazy imports: keep module import cheap and avoid hard deps at startup.
        from ai_design.providers.gemini import _extract_json
        from core.integrations import gemini_generate_from_image

        text = gemini_generate_from_image(
            _VISION_PROMPT, image_bytes, mime=_sniff_mime(image_bytes)
        )
        try:
            scene = _extract_json(text)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ApiException(
                "La IA de visión no devolvió un plano válido. Reintenta o prueba "
                "con otra imagen del plano.",
                code="inference_error", status_code=502,
            ) from exc

        scene.setdefault("walls", [])
        scene.setdefault("doors", [])
        scene.setdefault("windows", [])
        scene.setdefault("rooms", [])
        scene.setdefault("scale", {"wall_height": 2.7, "default_wall_thickness": 0.12})
        scene.setdefault("image", {"unit": "meters", "pixels_per_meter": None})
        scene.setdefault("meta", {"model": "gemini-vision", "version": "1.0"})
        return scene
