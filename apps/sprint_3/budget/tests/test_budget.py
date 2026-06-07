"""CU11/CU12/CU13 — materials catalog, budget computation and engineer review."""

from __future__ import annotations

from decimal import Decimal

import pytest

from accounts.models import Role
from budget.models import BlockQuality, Material, MaterialCategory
from projects.models import Project

pytestmark = pytest.mark.django_db


def _material(price="10.00"):
    category = MaterialCategory.objects.create(name="Mampostería")
    return Material.objects.create(
        category=category, name="Bloque", unit="unidad",
        unit_price=Decimal(price), block_quality=BlockQuality.STANDARD,
    )


def test_material_write_requires_superadmin(make_user, auth_client):
    category = MaterialCategory.objects.create(name="Cat")
    payload = {"category": category.id, "name": "X", "unit": "u",
               "unit_price": "5.00", "block_quality": "standard"}

    cliente = auth_client(make_user(role=Role.CLIENTE))
    assert cliente.post("/api/materials/", payload, format="json").status_code == 403

    admin = auth_client(make_user(email="s@x.dev", role=Role.SUPERADMIN))
    assert admin.post("/api/materials/", payload, format="json").status_code == 201


def test_material_catalog_readable_by_any_user(make_user, auth_client):
    _material()
    client = auth_client(make_user())
    resp = client.get("/api/materials/")
    assert resp.status_code == 200
    assert resp.json()["meta"]["pagination"]["count"] == 1


def test_create_budget_computes_total(make_user, auth_client):
    user = make_user()
    project = Project.objects.create(owner=user, name="P")
    material = _material("10.00")
    client = auth_client(user)
    resp = client.post(
        "/api/budgets/",
        {"project": project.id, "labor_people": 3, "labor_cost": "100.00",
         "items": [{"material": material.id, "quantity": "5"}]},
        format="json",
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["materials_cost"] == "50.00"
    assert data["total"] == "150.00"
    assert data["items"][0]["subtotal"] == "50.00"


def test_submit_then_engineer_review(make_user, auth_client):
    owner = make_user(email="o@x.dev")
    engineer = make_user(email="i@x.dev", role=Role.INGENIERO)
    project = Project.objects.create(owner=owner, name="P")
    material = _material("10.00")

    owner_client = auth_client(owner)
    budget_id = owner_client.post(
        "/api/budgets/",
        {"project": project.id, "items": [{"material": material.id, "quantity": "2"}]},
        format="json",
    ).json()["data"]["id"]

    submitted = owner_client.post(f"/api/budgets/{budget_id}/submit/")
    assert submitted.status_code == 200
    assert submitted.json()["data"]["status"] == "submitted"

    # The project owner (cliente) cannot review.
    denied = owner_client.post(
        f"/api/budgets/{budget_id}/review/", {"decision": "approved"}, format="json"
    )
    assert denied.status_code == 403

    # The engineer approves.
    engineer_client = auth_client(engineer)
    reviewed = engineer_client.post(
        f"/api/budgets/{budget_id}/review/",
        {"decision": "approved", "comments": "Conforme"}, format="json",
    )
    assert reviewed.status_code == 200
    body = reviewed.json()["data"]
    assert body["status"] == "approved"
    assert body["review"]["decision"] == "approved"
