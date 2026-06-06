"""Deterministic heuristic risk analyzer (no API key needed).

Applies simple, explainable structural rules to the scene geometry so CU10/CU11
work offline. Not a substitute for engineering judgement.
"""

from __future__ import annotations

import math

from .base import RiskAnalyzerBase

_LONG_WALL_M = 6.0
_LARGE_AREA_M2 = 40.0
_MIN_DOOR_W = 0.8


def _wall_length(wall: dict) -> float:
    s, e = wall.get("start") or {}, wall.get("end") or {}
    return math.hypot(
        float(e.get("x", 0)) - float(s.get("x", 0)),
        float(e.get("y", 0)) - float(s.get("y", 0)),
    )


class MockRiskAnalyzer(RiskAnalyzerBase):
    name = "mock"

    def analyze(self, scene_json: dict) -> dict:
        scene_json = scene_json or {}
        walls = scene_json.get("walls") or []
        doors = scene_json.get("doors") or []
        findings: list[dict] = []

        if not walls:
            findings.append({
                "category": "estructura",
                "severity": "critical",
                "description": "El modelo no contiene muros.",
                "suggestion": "Genera o importa una geometría con muros antes de evaluar riesgos.",
            })

        for wall in walls:
            length = _wall_length(wall)
            if length > _LONG_WALL_M:
                findings.append({
                    "category": "muros",
                    "severity": "high",
                    "description": f"Muro '{wall.get('id')}' de {length:.1f} m sin apoyo intermedio.",
                    "suggestion": "Añadir una columna o muro de arriostramiento a mitad de tramo.",
                })

        bounds = scene_json.get("bounds") or {}
        try:
            area = (float(bounds["max_x"]) - float(bounds["min_x"])) * (
                float(bounds["max_y"]) - float(bounds["min_y"])
            )
        except (KeyError, TypeError, ValueError):
            area = 0.0
        if area > _LARGE_AREA_M2:
            findings.append({
                "category": "luz",
                "severity": "medium",
                "description": f"Área de {area:.0f} m² sin subdivisión; posible luz excesiva.",
                "suggestion": "Revisar el dimensionamiento de losa/vigas para esa luz.",
            })

        for door in doors:
            if float(door.get("width") or 0) < _MIN_DOOR_W:
                findings.append({
                    "category": "accesibilidad",
                    "severity": "low",
                    "description": f"Puerta '{door.get('id')}' de {door.get('width')} m, estrecha.",
                    "suggestion": "Ampliar el vano a ≥ 0.80 m para accesibilidad.",
                })

        summary = (
            "Sin observaciones de riesgo con las reglas básicas."
            if not findings else
            f"{len(findings)} observación(es) de riesgo detectada(s)."
        )
        return {"summary": summary, "findings": findings}
