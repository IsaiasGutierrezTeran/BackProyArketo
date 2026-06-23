"""Business logic for AI design (views only orchestrate)."""

from __future__ import annotations

from django.conf import settings
from django.db import transaction

from core.exceptions import ApiException
from modeling.services import create_model_from_scene
from projects.services import assert_can_edit_project, projects_for

from .models import DesignMode, DesignRequest, DesignStatus
from .providers import (
    AwsDesignProvider,
    DesignProviderBase,
    GeminiDesignProvider,
    MockDesignProvider,
)
from .stt import get_transcriber

_PROVIDERS: dict[str, type[DesignProviderBase]] = {
    "mock": MockDesignProvider,
    "gemini": GeminiDesignProvider,
    "aws": AwsDesignProvider,
}


def get_provider(name: str | None = None) -> DesignProviderBase:
    name = name or settings.AI_DESIGN_PROVIDER
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ApiException(
            f"Proveedor de IA desconocido '{name}'. Opciones: {', '.join(_PROVIDERS)}.",
            code="bad_request",
        )
    return cls()


def _resolve_project(user, project_id: int | None):
    if not project_id:
        return None
    project = projects_for(user).filter(pk=project_id).first()
    if project is None:
        raise ApiException("Proyecto no encontrado.", code="not_found", status_code=404)
    return project


def generate_from_text(*, user, prompt: str, project_id: int | None = None,
                       provider_name: str | None = None,
                       mode: str = DesignMode.TEXT, transcript: str = "") -> DesignRequest:
    """Generate a scene from a brief and (if a project is given) a 3D model (CU9)."""
    project = _resolve_project(user, project_id)
    if project is not None:
        assert_can_edit_project(user, project)  # a viewer can't add a model
    provider = get_provider(provider_name)
    request = DesignRequest.objects.create(
        user=user, project=project, mode=mode, prompt_text=prompt,
        transcript=transcript, provider=provider.name, status=DesignStatus.PENDING,
    )
    try:
        # La llamada al proveedor (posible red/LLM) queda FUERA de la transacción
        # para no mantener abierta una conexión de BD durante la inferencia.
        try:
            scene = provider.generate_scene(prompt)
        except Exception:  # noqa: BLE001 — IA externa falló (429/cuota/red): usar el mock
            if provider.name == "mock":
                raise
            scene = MockDesignProvider().generate_scene(prompt)
            scene.setdefault("meta", {})["fallback_from"] = provider.name
            request.provider = f"{provider.name}->mock"
        with transaction.atomic():
            model = (
                create_model_from_scene(project=project, scene_json=scene)
                if project else None
            )
    except ApiException as exc:
        request.status = DesignStatus.FAILED
        request.error = str(exc.detail)[:2000]
        request.save(update_fields=["status", "error", "updated_at"])
        raise
    except Exception as exc:  # noqa: BLE001 — cualquier fallo no controlado deja FAILED, no PENDING
        request.status = DesignStatus.FAILED
        request.error = str(exc)[:2000]
        request.save(update_fields=["status", "error", "updated_at"])
        raise ApiException(
            "No se pudo generar el diseño. Reintenta más tarde.",
            code="inference_error", status_code=502,
        ) from exc

    request.result = {"scene": scene}
    request.model3d = model
    request.status = DesignStatus.COMPLETED
    request.save(update_fields=["result", "model3d", "status", "updated_at"])
    return request


def generate_from_audio(*, user, audio_file, project_id: int | None = None,
                        provider_name: str | None = None) -> DesignRequest:
    """Transcribe audio, then generate from the transcript (CU9)."""
    transcriber = get_transcriber()
    audio_file.seek(0)
    transcript = transcriber.transcribe(audio_file.read(), filename=audio_file.name)

    request = generate_from_text(
        user=user, prompt=transcript, project_id=project_id,
        provider_name=provider_name, mode=DesignMode.AUDIO, transcript=transcript,
    )
    audio_file.seek(0)
    request.audio_file.save(audio_file.name, audio_file, save=True)
    return request


def assistant_reply(*, user, message: str, request_id: int | None = None,
                    project_id: int | None = None,
                    provider_name: str | None = None) -> DesignRequest:
    """Append a turn to an assistant conversation and return the reply (CU9)."""
    provider = get_provider(provider_name)
    if request_id:
        request = DesignRequest.objects.filter(
            pk=request_id, user=user, mode=DesignMode.ASSISTANT
        ).first()
        if request is None:
            raise ApiException("Conversación no encontrada.", code="not_found", status_code=404)
    else:
        request = DesignRequest.objects.create(
            user=user, project=_resolve_project(user, project_id),
            mode=DesignMode.ASSISTANT, provider=provider.name,
            status=DesignStatus.COMPLETED, result={"messages": []},
        )

    messages = list((request.result or {}).get("messages", []))
    messages.append({"role": "user", "content": message})
    try:
        reply = provider.chat(messages)
    except Exception:  # noqa: BLE001 — IA externa caída (429/cuota): responde el asistente mock
        if provider.name == "mock":
            raise
        reply = MockDesignProvider().chat(messages)
    messages.append({"role": "assistant", "content": reply})

    request.result = {"messages": messages}
    request.provider = provider.name
    request.save(update_fields=["result", "provider", "updated_at"])
    return request
