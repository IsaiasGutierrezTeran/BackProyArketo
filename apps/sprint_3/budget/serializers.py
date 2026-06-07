"""Serializers (I/O only) for the materials catalog and budgets."""

from __future__ import annotations

from rest_framework import serializers

from .models import (
    Budget,
    BudgetItem,
    BudgetReview,
    Material,
    MaterialCategory,
)


class MaterialCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialCategory
        fields = ["id", "name"]


class MaterialSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Material
        fields = [
            "id", "category", "category_name", "name", "unit",
            "unit_price", "block_quality", "is_active",
        ]


class BudgetItemSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source="material.name", read_only=True)

    class Meta:
        model = BudgetItem
        fields = [
            "id", "material", "material_name", "quantity",
            "unit_price_snapshot", "subtotal",
        ]
        read_only_fields = ["id", "unit_price_snapshot", "subtotal", "material_name"]


class BudgetReviewSerializer(serializers.ModelSerializer):
    reviewer_email = serializers.EmailField(source="reviewer.email", read_only=True)

    class Meta:
        model = BudgetReview
        fields = ["id", "reviewer_email", "decision", "comments", "created_at"]
        read_only_fields = fields


class BudgetSerializer(serializers.ModelSerializer):
    items = BudgetItemSerializer(many=True, read_only=True)
    review = BudgetReviewSerializer(read_only=True)
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)

    class Meta:
        model = Budget
        fields = [
            "id", "project", "created_by_email", "status",
            "labor_people", "labor_cost", "materials_cost", "total", "currency",
            "items", "review", "created_at", "updated_at",
        ]
        read_only_fields = fields


# --- Input serializers ------------------------------------------------------
class BudgetItemInputSerializer(serializers.Serializer):
    material = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)


class BudgetCreateSerializer(serializers.Serializer):
    project = serializers.IntegerField(min_value=1)
    labor_people = serializers.IntegerField(min_value=0, default=0)
    labor_cost = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=0, default=0
    )
    currency = serializers.CharField(max_length=8, required=False)
    items = BudgetItemInputSerializer(many=True)


class BudgetReviewInputSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approved", "observed", "rejected"])
    comments = serializers.CharField(required=False, allow_blank=True)
