"""PDF report builders for risk analyses (HU-10) and budgets (HU-12).

reportlab is imported lazily inside each builder so that importing this module
(and the views that use it) never fails when the optional dependency is absent;
the endpoint then surfaces a clear error instead of breaking app startup.
"""

from __future__ import annotations

import io

from core.exceptions import ApiException

_SEVERITY_ES = {"low": "Baja", "medium": "Media", "high": "Alta", "critical": "Crítica"}
_SEVERITY_HEX = {
    "low": "#2e7d32", "medium": "#f9a825", "high": "#ef6c00", "critical": "#c62828",
}


def _reportlab():
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )
    except ImportError as exc:  # pragma: no cover
        raise ApiException(
            "La generación de PDF no está disponible (falta reportlab).",
            code="inference_error", status_code=503,
        ) from exc
    return colors, A4, getSampleStyleSheet, mm, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def risk_report_pdf(analysis) -> bytes:
    """Build the structural-risk report for a RiskAnalysis (HU-10)."""
    (colors, A4, get_styles, mm, Paragraph, SimpleDocTemplate, Spacer,
     Table, TableStyle) = _reportlab()
    styles = get_styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, title=f"Análisis de riesgos #{analysis.id}",
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
    )
    story = [
        Paragraph("Arketo — Análisis de riesgos estructurales", styles["Title"]),
        Paragraph(
            f"Análisis #{analysis.id} · Modelo 3D #{analysis.model3d_id} · "
            f"Proveedor: {analysis.provider or 'n/d'} · Estado: {analysis.get_status_display()}",
            styles["Normal"],
        ),
        Spacer(1, 6 * mm),
    ]
    if analysis.summary:
        story += [Paragraph("Resumen", styles["Heading2"]),
                  Paragraph(analysis.summary, styles["Normal"]), Spacer(1, 4 * mm)]

    findings = list(analysis.findings.all())
    if not findings:
        story.append(Paragraph("No se detectaron riesgos en este modelo.", styles["Normal"]))
    else:
        rows = [["#", "Severidad", "Categoría", "Descripción", "Recomendación"]]
        for i, f in enumerate(findings, start=1):
            rows.append([
                str(i), _SEVERITY_ES.get(f.severity, f.severity), f.category,
                Paragraph(f.description, styles["BodyText"]),
                Paragraph(f.suggestion or "—", styles["BodyText"]),
            ])
        table = Table(rows, colWidths=[8 * mm, 20 * mm, 30 * mm, 60 * mm, 56 * mm], repeatRows=1)
        style = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#11151c")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f9")]),
        ])
        for r, f in enumerate(findings, start=1):
            style.add("TEXTCOLOR", (1, r), (1, r),
                      colors.HexColor(_SEVERITY_HEX.get(f.severity, "#000000")))
        table.setStyle(style)
        story += [Paragraph(f"Riesgos detectados: {len(findings)}", styles["Heading2"]), table]

    doc.build(story)
    return buf.getvalue()


def budget_report_pdf(budget) -> bytes:
    """Build the budget breakdown report for a Budget (HU-12)."""
    (colors, A4, get_styles, mm, Paragraph, SimpleDocTemplate, Spacer,
     Table, TableStyle) = _reportlab()
    styles = get_styles()
    cur = budget.currency or ""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, title=f"Presupuesto #{budget.id}",
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
    )
    story = [
        Paragraph("Arketo — Presupuesto de obra", styles["Title"]),
        Paragraph(
            f"Presupuesto #{budget.id} · Proyecto #{budget.project_id} · "
            f"Estado: {budget.get_status_display()} · Autor: "
            f"{getattr(budget.created_by, 'email', 'n/d')}",
            styles["Normal"],
        ),
        Spacer(1, 6 * mm),
        Paragraph("Materiales", styles["Heading2"]),
    ]

    rows = [["Material", "Cantidad", "P. unit.", "Subtotal"]]
    for it in budget.items.select_related("material").all():
        rows.append([
            Paragraph(it.material.name, styles["BodyText"]),
            f"{it.quantity}", f"{it.unit_price_snapshot} {cur}", f"{it.subtotal} {cur}",
        ])
    table = Table(rows, colWidths=[78 * mm, 28 * mm, 33 * mm, 35 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#11151c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f9")]),
    ]))
    story += [table, Spacer(1, 6 * mm), Paragraph("Resumen", styles["Heading2"])]

    summary = [
        ["Costo de materiales", f"{budget.materials_cost} {cur}"],
        [f"Mano de obra ({budget.labor_people} personas)", f"{budget.labor_cost} {cur}"],
        ["TOTAL", f"{budget.total} {cur}"],
    ]
    stable = Table(summary, colWidths=[120 * mm, 54 * mm])
    stable.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    story.append(stable)

    review = getattr(budget, "review", None)
    if review is not None:
        story += [
            Spacer(1, 6 * mm), Paragraph("Revisión del ingeniero", styles["Heading2"]),
            Paragraph(
                f"Decisión: {review.decision} · Revisor: "
                f"{getattr(review.reviewer, 'email', 'n/d')}", styles["Normal"]),
        ]
        if review.comments:
            story.append(Paragraph(f"Observaciones: {review.comments}", styles["Normal"]))

    doc.build(story)
    return buf.getvalue()
