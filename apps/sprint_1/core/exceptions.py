"""Centralized error handling and the uniform error envelope.

Every error response has the shape::

    {"success": false, "error": {"code": <machine code>, "detail": <message|dict>}}

Business code raises :class:`ApiException` (or DRF's own exceptions) and this
handler turns it into that envelope. The renderer detects the ``success`` key
and passes the body through unchanged (no double wrapping).
"""

from __future__ import annotations

from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

# Defined in a DRF-free module to avoid an import cycle
# (renderers -> exceptions -> DRF settings -> renderers). Re-exported here.
from .error_codes import STATUS_ERROR_CODES, error_code_for  # noqa: F401


class ApiException(APIException):
    """Base for business errors raised from the service layer.

    Subclass or instantiate with a ``code`` to control the envelope's error code.
    """

    status_code = 400
    default_detail = "Solicitud inválida."
    default_code = "bad_request"

    def __init__(
        self,
        detail=None,
        code: str | None = None,
        status_code: int | None = None,
    ):
        if status_code is not None:
            self.status_code = status_code
        self._code = code or self.default_code
        super().__init__(detail=detail or self.default_detail, code=self._code)


class Conflict(ApiException):
    status_code = 409
    default_detail = "Conflicto con el estado actual del recurso."
    default_code = "conflict"


def api_exception_handler(exc, context):
    """Wrap DRF's default error output in ``{success: false, error: {...}}``."""
    response = drf_exception_handler(exc, context)
    if response is None:
        # Non-DRF exception -> let Django produce a 500 (DEBUG shows the traceback).
        return None

    code = getattr(exc, "_code", None) or error_code_for(response.status_code)
    detail = response.data
    # Collapse DRF's ``{"detail": "..."}`` to just the message.
    if isinstance(detail, dict) and "detail" in detail and len(detail) == 1:
        detail = detail["detail"]

    response.data = {
        "success": False,
        "error": {"code": code, "detail": detail},
    }
    return Response(
        response.data,
        status=response.status_code,
        headers=_safe_headers(response),
    )


def _safe_headers(response) -> dict:
    """Preserve auth-relevant headers (e.g. WWW-Authenticate) on the new Response."""
    headers = {}
    for key in ("WWW-Authenticate",):
        if key in response.headers:
            headers[key] = response.headers[key]
    return headers
