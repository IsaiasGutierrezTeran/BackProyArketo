"""Stable HTTP-status -> error-code mapping.

Kept dependency-free (no DRF imports) so both `core.exceptions` and
`core.renderers` can use it without creating an import cycle.
"""

from __future__ import annotations

STATUS_ERROR_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    406: "not_acceptable",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "throttled",
    500: "internal_error",
}


def error_code_for(status_code: int) -> str:
    return STATUS_ERROR_CODES.get(status_code, "error")
