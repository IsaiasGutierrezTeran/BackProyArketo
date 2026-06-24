"""CU9 — generate from text/audio and conversational assistant (mock provider)."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import Role
from modeling.models import Model3D
from projects.models import Project

pytestmark = pytest.mark.django_db


def test_text_generates_scene_and_model(make_user, auth_client):
    user = make_user(role=Role.ARQUITECTO)
    project = Project.objects.create(owner=user, name="P")
    client = auth_client(user)
    resp = client.post(
        "/api/ai-design/text",
        {"prompt": "una casa de 6 x 4 metros", "project": project.id},
        format="json",
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["status"] == "completed"
    assert data["model"]["element_count"] >= 4
    assert Model3D.objects.filter(project=project).exists()


def test_text_without_project_has_no_model(make_user, auth_client):
    client = auth_client(make_user(role=Role.ARQUITECTO))
    resp = client.post(
        "/api/ai-design/text", {"prompt": "un cuarto"}, format="json"
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["model"] is None


def test_assistant_appends_reply(make_user, auth_client):
    client = auth_client(make_user(role=Role.ARQUITECTO))
    resp = client.post(
        "/api/ai-design/assistant",
        {"message": "hola, quiero una casa"},
        format="json",
    )
    assert resp.status_code == 201
    messages = resp.json()["data"]["result"]["messages"]
    assert len(messages) == 2
    assert messages[1]["role"] == "assistant"


def test_audio_transcribes_and_generates(make_user, auth_client):
    user = make_user(role=Role.ARQUITECTO)
    project = Project.objects.create(owner=user, name="P")
    client = auth_client(user)
    audio = SimpleUploadedFile(
        "voz.wav", b"RIFF0000WAVE", content_type="audio/wav"
    )
    resp = client.post(
        "/api/ai-design/audio",
        {"audio": audio, "project": project.id},
        format="multipart",
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["mode"] == "audio"
    assert data["transcript"]
