"""프로젝트 목록·생성 API(projects_api.py) — 기존 test_tasks_api.py와 동일한 monkeypatch
격리 패턴(TestClient + get_project_registry 교체, CRZ)."""

import pytest
from fastapi.testclient import TestClient

from backend.adapters.api import projects_api
from backend.adapters.persistence.project_registry import DEFAULT_PROJECT_ID, ProjectRegistry
from backend.server import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    monkeypatch.setattr(projects_api, "get_project_registry", lambda: registry)
    return TestClient(app), registry


def test_list_projects_includes_default_when_empty(client):
    test_client, _ = client
    res = test_client.get("/projects")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    ids = [p["id"] for p in body["data"]["projects"]]
    assert DEFAULT_PROJECT_ID in ids


def test_create_project_success(client):
    test_client, _ = client
    res = test_client.post("/projects", json={"name": "새 프로젝트"})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["name"] == "새 프로젝트"
    assert body["data"]["id"] != DEFAULT_PROJECT_ID

    listed = test_client.get("/projects").json()
    ids = [p["id"] for p in listed["data"]["projects"]]
    assert body["data"]["id"] in ids


def test_create_project_empty_name_returns_422(client):
    test_client, _ = client
    res = test_client.post("/projects", json={"name": "   "})
    assert res.status_code == 422
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "AEGIS-VALIDATION"


def test_create_project_missing_name_field_returns_422(client):
    test_client, _ = client
    res = test_client.post("/projects", json={})
    assert res.status_code == 422
