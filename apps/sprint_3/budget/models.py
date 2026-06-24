"""Materials catalog and construction budgets."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import BaseModel


class BlockQuality(models.TextChoices):
    LOW = "low", "Baja"
    STANDARD = "standard", "Estándar"
    HIGH = "high", "Alta"


class MaterialCategory(BaseModel):
    name = models.CharField(max_length=80, unique=True)

    class Meta(BaseModel.Meta):
        verbose_name_plural = "material categories"

    def __str__(self) -> str:
        return self.name


class Material(BaseModel):
    category = models.ForeignKey(
        MaterialCategory, on_delete=models.PROTECT, related_name="materials"
    )
    name = models.CharField(max_length=120)
    unit = models.CharField(max_length=20, help_text="m², m³, saco, unidad…")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    block_quality = models.CharField(
        max_length=12,
        choices=BlockQuality.choices,
        default=BlockQuality.STANDARD,
    )
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.block_quality})"


class BudgetStatus(models.TextChoices):
    DRAFT = "draft", "Borrador"
    SUBMITTED = "submitted", "Enviado"
    APPROVED = "approved", "Aprobado"
    OBSERVED = "observed", "Observado"
    REJECTED = "rejected", "Rechazado"


class Budget(BaseModel):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="budgets"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="budgets",
    )
    status = models.CharField(
        max_length=12, choices=BudgetStatus.choices, default=BudgetStatus.DRAFT
    )
    # Mano de obra: number of workers + their total cost.
    labor_people = models.PositiveIntegerField(default=0)
    labor_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=0
    )
    materials_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=0
    )
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="USD")

    def __str__(self) -> str:
        return f"Budget #{self.pk} (project {self.project_id}, {self.status})"


class BudgetItem(BaseModel):
    budget = models.ForeignKey(
        Budget, on_delete=models.CASCADE, related_name="items"
    )
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name="+"
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    # Price captured at creation time so later catalog changes don't alter the budget.
    unit_price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.quantity} x {self.material_id}"


class ReviewDecision(models.TextChoices):
    APPROVED = "approved", "Aprobado"
    OBSERVED = "observed", "Observado"
    REJECTED = "rejected", "Rechazado"


class BudgetReview(BaseModel):
    budget = models.OneToOneField(
        Budget, on_delete=models.CASCADE, related_name="review"
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="budget_reviews",
    )
    decision = models.CharField(max_length=12, choices=ReviewDecision.choices)
    comments = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"Review of budget {self.budget_id}: {self.decision}"
