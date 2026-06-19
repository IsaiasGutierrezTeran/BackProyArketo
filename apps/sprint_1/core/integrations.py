"""Thin, optional Google Gemini client (used by ai_design and risk).

Kept tiny and guarded: callers select providers ("mock" by default), so the real
API is only hit when explicitly configured with GEMINI_API_KEY.
"""

from __future__ import annotations

import requests
from django.conf import settings

from .exceptions import ApiException

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def gemini_generate_text(prompt: str, *, timeout: float = 60.0) -> str:
    """Call Gemini's generateContent and return the first candidate's text."""
    key = settings.GEMINI_API_KEY
    if not key:
        raise ApiException(
            "GEMINI_API_KEY no está configurada.", code="bad_request", status_code=400
        )
    url = _GEMINI_URL.format(model=settings.GEMINI_MODEL)
    try:
        resp = requests.post(
            url,
            params={"key": key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise ApiException(
            "No se pudo contactar el servicio de IA (Gemini).",
            code="inference_error", status_code=502,
        ) from exc
    if resp.status_code != 200:
        raise ApiException(
            f"El servicio de IA respondió {resp.status_code}.",
            code="inference_error", status_code=502,
        )
    try:
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, ValueError) as exc:
        raise ApiException(
            "Respuesta inesperada del servicio de IA.",
            code="inference_error", status_code=502,
        ) from exc


def gemini_generate_from_image(
    prompt: str, image_bytes: bytes, *, mime: str = "image/png", timeout: float = 120.0
) -> str:
    """Call Gemini's generateContent with an image + text and return the text.

    Used by the vision detector: a multimodal model can read colored/rendered
    plans (and their written dimensions) that the legacy Mask R-CNN cannot.
    """
    import base64

    key = settings.GEMINI_API_KEY
    if not key:
        raise ApiException(
            "GEMINI_API_KEY no está configurada.", code="bad_request", status_code=400
        )
    url = _GEMINI_URL.format(model=settings.GEMINI_MODEL)
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime,
                                     "data": base64.b64encode(image_bytes).decode()}},
                ]
            }
        ]
    }
    try:
        resp = requests.post(url, params={"key": key}, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise ApiException(
            "No se pudo contactar el servicio de IA (Gemini).",
            code="inference_error", status_code=502,
        ) from exc
    if resp.status_code != 200:
        raise ApiException(
            f"El servicio de IA respondió {resp.status_code}.",
            code="inference_error", status_code=502,
        )
    try:
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, ValueError) as exc:
        raise ApiException(
            "Respuesta inesperada del servicio de IA.",
            code="inference_error", status_code=502,
        ) from exc
