"""Entitlements por plan de suscripción (monetización).

El plan del usuario (``user.subscription_plan``: free | pro | enterprise) habilita
features. Se enforza en la capa de VISTAS (no en services) para no romper
seeders / back-office, que crean datos directamente por la capa de servicios.

Matriz:
    Free        -> 1 proyecto, solo detección mock.
    Pro         -> proyectos ilimitados, Mask R-CNN / IA visión, Riesgos IA.
    Enterprise  -> todo Pro + Colaboración (invitar).
El superadmin no tiene límites.
"""

from __future__ import annotations

from core.exceptions import ApiException

PLAN_ORDER = {"free": 0, "pro": 1, "enterprise": 2}

# Límite de proyectos propios por plan (None = ilimitado).
MAX_PROJECTS = {"free": 1, "pro": None, "enterprise": None}

# Detectores permitidos por plan.
DETECTORS = {
    "free": {"mock"},
    "pro": {"mock", "maskrcnn", "gemini-vision"},
    "enterprise": {"mock", "maskrcnn", "gemini-vision"},
}

_PLAN_LABEL = {"free": "Free", "pro": "Pro", "enterprise": "Enterprise"}


def plan_of(user) -> str:
    """Plan efectivo del usuario; superadmin se trata como enterprise (sin límites)."""
    if getattr(user, "is_superadmin", False):
        return "enterprise"
    return (getattr(user, "subscription_plan", "") or "free").lower()


def _rank(plan: str) -> int:
    return PLAN_ORDER.get(plan, 0)


def project_limit(user) -> int | None:
    """Máximo de proyectos propios (None = ilimitado)."""
    return MAX_PROJECTS.get(plan_of(user), 1)


def allowed_detectors(user) -> set[str]:
    return DETECTORS.get(plan_of(user), {"mock"})


def requires_plan(user, minimum: str, feature: str = "Esta función") -> None:
    """Lanza 403 si el plan del usuario es inferior a ``minimum``."""
    if _rank(plan_of(user)) < _rank(minimum):
        raise ApiException(
            f"{feature} requiere el plan {_PLAN_LABEL.get(minimum, minimum)} o superior. "
            "Mejora tu suscripción.",
            code="forbidden",
            status_code=403,
        )
