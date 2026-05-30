"""drf-spectacular post-processing: reflect the response envelope in the schema.

Wraps every 2xx response schema as ``{success, data, meta}`` so the generated
OpenAPI / Swagger matches what clients actually receive.
"""

from __future__ import annotations


def _wrap(inner_schema: dict) -> dict:
    return {
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "example": True},
            "data": inner_schema,
            "meta": {"type": "object", "example": {}},
        },
        "required": ["success", "data"],
    }


def envelope_postprocessing_hook(result, generator, request, public):
    for path_item in result.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            for code, response in operation.get("responses", {}).items():
                if not str(code).startswith("2"):
                    continue
                for media in response.get("content", {}).values():
                    if "schema" in media:
                        media["schema"] = _wrap(media["schema"])
    return result
