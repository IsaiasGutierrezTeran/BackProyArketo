"""Detection pipeline: plan image -> detector -> normalized scene -> 3D model."""

from __future__ import annotations

import time

from core.exceptions import ApiException
from modeling.services import create_model_from_scene
from plans.models import Plan, PlanStatus

from .detectors import (
    DetectorBase,
    MaskRCNNDetector,
    MockDetector,
    VisionLLMDetector,
)
from .models import DetectionJob, JobStatus

_DETECTORS: dict[str, type[DetectorBase]] = {
    "mock": MockDetector,
    "maskrcnn": MaskRCNNDetector,
    "gemini-vision": VisionLLMDetector,
}


def get_detector(name: str | None = None) -> DetectorBase:
    from django.conf import settings

    name = name or settings.DETECTION_DEFAULT_DETECTOR
    cls = _DETECTORS.get(name)
    if cls is None:
        raise ApiException(
            f"Detector desconocido '{name}'. Opciones: {', '.join(_DETECTORS)}.",
            code="bad_request",
        )
    return cls()


def _read_image_bytes(plan: Plan) -> bytes:
    plan.file.open("rb")
    try:
        return plan.file.read()
    finally:
        plan.file.close()


def run_pipeline(
    *,
    plan: Plan,
    detector_name: str | None = None,
    options: dict | None = None,
) -> DetectionJob:
    """Run detection for a plan and build its 3D model. Persists a DetectionJob."""
    detector = get_detector(detector_name)
    job = DetectionJob.objects.create(
        plan=plan, detector=detector.name, status=JobStatus.RUNNING
    )
    plan.status = PlanStatus.PROCESSING
    plan.save(update_fields=["status", "updated_at"])

    started = time.perf_counter()
    try:
        scene = detector.detect(_read_image_bytes(plan), options=options or {})
        if not (scene.get("walls")):
            raise ApiException(
                "No se detectaron muros en este plano. Sube un plano técnico de "
                "líneas (preferible blanco y negro), prueba el detector de visión "
                "IA, o usa 'Diseñar con IA' por texto.",
                code="unprocessable",
                status_code=422,
            )
        model3d = create_model_from_scene(
            project=plan.project,
            scene_json=scene,
            source_plan=plan,
        )
    except ApiException:
        _fail(job, plan, "Detección fallida.")
        raise
    except Exception as exc:  # noqa: BLE001 — record any failure on the job
        _fail(job, plan, str(exc))
        raise ApiException(
            "Error durante la generación del modelo 3D.",
            code="inference_error",
            status_code=500,
        ) from exc

    job.raw_result = scene
    job.model3d = model3d
    job.processing_ms = int((time.perf_counter() - started) * 1000)
    job.status = JobStatus.COMPLETED
    job.save()

    plan.status = PlanStatus.PROCESSED
    plan.save(update_fields=["status", "updated_at"])
    return job


def _fail(job: DetectionJob, plan: Plan, message: str) -> None:
    job.status = JobStatus.FAILED
    job.error = message[:2000]
    job.save(update_fields=["status", "error", "updated_at"])
    plan.status = PlanStatus.FAILED
    plan.save(update_fields=["status", "updated_at"])
