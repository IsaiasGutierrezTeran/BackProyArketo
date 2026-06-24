"""HU-13 — engineer can reject a submitted budget (terminal state)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from accounts.models import Role
from budget.models import Material, MaterialCategory
from projects.models import Project

pytestmark = pytest.mark.django_db


def _make_submitted_budget(owner, auth_client):
    category = MaterialCategory.objects.create(name="Cementos")
    material = Material.objects.create(
        category=category,
        name="Cemento",
        unit="saco",
        unit_price=Decimal("50"),
    )
    project = Project.objects.create(owner=owner, name="P")
    client = auth_client(owner)
    created = client.post(
        "/api/budgets/",
        {
            "project": project.id,
            "items": [{"material": material.id, "quantity": 2}],
        },
        format="json",
    ).json()["data"]
    client.post(f"/api/budgets/{created['id']}/submit/")
    return created["id"]


def test_engineer_rejects_budget(make_user, auth_client):
    owner = make_user(email="owner@test.dev")
    budget_id = _make_submitted_budget(owner, auth_client)

    engineer = auth_client(
        make_user(email="ing@test.dev", role=Role.INGENIERO)
    )
    resp = engineer.post(
        f"/api/budgets/{budget_id}/review/",
        {"decision": "rejected", "comments": "Excede el presupuesto."},
        format="json",
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "rejected"
    assert data["review"]["decision"] == "rejected"


def test_rejected_budget_cannot_be_resubmitted(make_user, auth_client):
    owner = make_user(email="owner2@test.dev")
    budget_id = _make_submitted_budget(owner, auth_client)
    engineer = auth_client(
        make_user(email="ing2@test.dev", role=Role.INGENIERO)
    )
    engineer.post(
        f"/api/budgets/{budget_id}/review/",
        {"decision": "rejected"},
        format="json",
    )

    # A rejected budget is terminal: submit is only allowed from draft/observed.
    owner_client = auth_client(owner)
    resp = owner_client.post(f"/api/budgets/{budget_id}/submit/")
    assert resp.status_code == 409
