"""Business logic for risk analysis (views only orchestrate)."""

from __future__ import annotations

from django.conf import settings
from django.db import transaction

from core.exceptions import ApiException
from projects.services import projects_for

from .analyzers import AwsRiskAnalyzer, GeminiRiskAnalyzer, MockRiskAnalyzer, RiskAnalyzerBase
from .models import AnalysisStatus, RiskAnalysis, RiskFinding, Severity

_ANALYZERS: dict[str, type[RiskAnalyzerBase]] = {
    "mock": MockRiskAnalyzer,
    "gemini": GeminiRiskAnalyzer,
    "aws": AwsRiskAnalyzer,
}
_VALID_SEVERITIES = {s.value for s in Severity}


def get_analyzer(name: str | None = None) -> RiskAnalyzerBase:
    name = name or settings.RISK_ANALYZER
    cls = _ANALYZERS.get(name)
    if cls is None:
        raise ApiException(
            f"Analizador desconocido '{name}'. Opciones: {', '.join(_ANALYZERS)}.",
            code="bad_request",
        )
    return cls()


def model_for_user(user, model3d_id: int):
    from modeling.models import Model3D

    model = (
        Model3D.objects.filter(pk=model3d_id, project__in=projects_for(user)).first()
    )
    if model is None:
        raise ApiException("Modelo 3D no encontrado.", code="not_found", status_code=404)
    return model


@transaction.atomic
def analyze_model(*, user, model3d, analyzer_name: str | None = None) -> RiskAnalysis:
    """Run the analyzer over a model's geometry and persist findings (CU10/CU11)."""
    analyzer = get_analyzer(analyzer_name)
    result = analyzer.analyze(model3d.scene_json or {})

    analysis = RiskAnalysis.objects.create(
        model3d=model3d, requested_by=user, provider=analyzer.name,
        status=AnalysisStatus.COMPLETED, summary=result.get("summary", ""),
    )
    findings = [
        RiskFinding(
            analysis=analysis,
            category=str(item.get("category", "general"))[:60],
            severity=item.get("severity") if item.get("severity") in _VALID_SEVERITIES else Severity.MEDIUM,
            description=str(item.get("description", "")),
            suggestion=str(item.get("suggestion", "")),
        )
        for item in result.get("findings", [])
    ]
    RiskFinding.objects.bulk_create(findings)
    return analysis
