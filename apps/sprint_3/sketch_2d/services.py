"""Lógica de HU-18 (las views solo orquestan)."""

from __future__ import annotations

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import QuerySet

from core.exceptions import ApiException
from projects.services import projects_for

from .models import Boceto2D, SketchStatus
from .providers import GeminiSketchProvider, MockSketchProvider, SketchProviderBase

_PROVIDERS: dict[str, type[SketchProviderBase]] = {
    "mock": MockSketchProvider,
    "gemini": GeminiSketchProvider,
}


def get_provider(name: str | None = None) -> SketchProviderBase:
    name = name or settings.SKETCH_PROVIDER
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ApiException(
            f"Proveedor desconocido '{name}'. Opciones: {', '.join(_PROVIDERS)}.",
            code="bad_request",
        )
    return cls()


def sketches_for(user) -> QuerySet[Boceto2D]:
    return Boceto2D.objects.filter(usuario=user)


def _resolve_project(user, project_id: int | None):
    if not project_id:
        return None
    project = projects_for(user).filter(pk=project_id).first()
    if project is None:
        raise ApiException("Proyecto no encontrado.", code="not_found", status_code=404)
    return project


def generate_sketch(*, user, prompt: str, project_id: int | None = None,
                    provider_name: str | None = None) -> Boceto2D:
    """Genera un boceto 2D, lo guarda y devuelve el `Boceto2D`.

    La URL absoluta de la imagen la calcula el serializer al leer (en S3 es
    prefirmada y se regenera en cada respuesta), por eso aquí no se persiste.
    """
    project = _resolve_project(user, project_id)
    provider = get_provider(provider_name)
    boceto = Boceto2D(usuario=user, proyecto=project, prompt=prompt, proveedor_ia=provider.name)

    try:
        png = provider.generate(prompt)
    except ApiException:
        boceto.estado = SketchStatus.ERROR
        boceto.save()
        raise

    boceto.imagen.save(f"sketch_{user.id}.png", ContentFile(png), save=False)
    boceto.estado = SketchStatus.GENERADO
    boceto.save()
    return boceto
