"""Success envelope renderer.

Wraps every successful response body as::

    {"success": true, "data": <payload>, "meta": {...}}

Paginated payloads (``{count, page, results, ...}``) are split so that
``data`` is the list and the pagination fields land under ``meta.pagination``.
Error bodies produced by :mod:`core.exceptions` already carry a ``success`` key
and are passed through unchanged.
"""

from __future__ import annotations

from rest_framework.renderers import JSONRenderer

from .error_codes import error_code_for


class EnvelopeJSONRenderer(JSONRenderer):
    """DRF renderer that applies the standard response envelope."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get("response")
        status_code = getattr(response, "status_code", 200) or 200

        # Already enveloped (exception handler) -> don't wrap twice.
        if isinstance(data, dict) and "success" in data and (
            "error" in data or "data" in data
        ):
            return super().render(data, accepted_media_type, renderer_context)

        if status_code >= 400:
            body = {
                "success": False,
                "error": {"code": error_code_for(status_code), "detail": data},
            }
        else:
            meta: dict = {}
            payload = data
            if isinstance(data, dict) and "results" in data and "count" in data:
                payload = data["results"]
                meta["pagination"] = {k: v for k, v in data.items() if k != "results"}
            body = {"success": True, "data": payload, "meta": meta}

        return super().render(body, accepted_media_type, renderer_context)
