"""Proveedor Gemini (Imagen) — opt-in con GEMINI_API_KEY + SKETCH_PROVIDER=gemini.

Llama a la API de generación de imágenes (Imagen) de Google. Si no hay clave o
falla, lanza ApiException (el modo por defecto es `mock`, que funciona sin clave).
"""

from __future__ import annotations

import base64

import requests
from django.conf import settings

from core.exceptions import ApiException

from .base import SketchProviderBase

_IMAGEN_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "imagen-3.0-generate-002:predict"
)


class GeminiSketchProvider(SketchProviderBase):
    name = "gemini"

    def generate(self, prompt: str) -> bytes:
        key = settings.GEMINI_API_KEY
        if not key:
            raise ApiException(
                "GEMINI_API_KEY no configurada; usa SKETCH_PROVIDER=mock.",
                code="bad_request", status_code=400,
            )
        body = {
            "instances": [{"prompt": f"Plano arquitectónico 2D, vista en planta: {prompt}"}],
            "parameters": {"sampleCount": 1},
        }
        try:
            resp = requests.post(_IMAGEN_URL, params={"key": key}, json=body, timeout=90)
        except requests.RequestException as exc:
            raise ApiException("No se pudo contactar el servicio de imágenes (Gemini).",
                               code="inference_error", status_code=502) from exc
        if resp.status_code != 200:
            raise ApiException(f"El servicio de imágenes respondió {resp.status_code}.",
                               code="inference_error", status_code=502)
        try:
            b64 = resp.json()["predictions"][0]["bytesBase64Encoded"]
            return base64.b64decode(b64)
        except (KeyError, IndexError, ValueError) as exc:
            raise ApiException("Respuesta inesperada del servicio de imágenes.",
                               code="inference_error", status_code=502) from exc
