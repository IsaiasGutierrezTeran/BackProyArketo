"""Real detector: delegates to the floorplan-api FastAPI service over HTTP.

The Mask R-CNN model is pinned to Python 3.6 / TF 1.15 and cannot run in this
process, so we call floorplan-api (which itself normalizes and, if configured,
proxies the legacy AIAPI Flask model). It already returns the normalized scene.
"""

from __future__ import annotations

import requests
from django.conf import settings

from core.exceptions import ApiException

from .base import DetectorBase

_PASSTHROUGH_PARAMS = (
    "pixels_per_meter",
    "confidence_threshold",
    "wall_height",
    "default_wall_thickness",
)


class MaskRCNNDetector(DetectorBase):
    name = "maskrcnn"

    def detect(
        self, image_bytes: bytes, *, options: dict | None = None
    ) -> dict:
        options = options or {}
        params = {
            k: options[k]
            for k in _PASSTHROUGH_PARAMS
            if options.get(k) is not None
        }
        url = f"{settings.FLOORPLAN_API_URL}/detect"
        try:
            resp = requests.post(
                url,
                files={"file": ("plan.png", image_bytes, "image/png")},
                params=params,
                timeout=settings.FLOORPLAN_API_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ApiException(
                "No se pudo contactar el servicio de detección (floorplan-api). "
                "¿Está corriendo en FLOORPLAN_API_URL?",
                code="inference_error",
                status_code=502,
            ) from exc

        if resp.status_code != 200:
            raise ApiException(
                f"El servicio de detección respondió {resp.status_code}.",
                code="inference_error",
                status_code=502,
            )
        return resp.json()
