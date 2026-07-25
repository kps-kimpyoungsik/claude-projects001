"""프로젝트 설정 영속화 API(project_config_api.py) — doc_types_api 테스트와 동일 패턴(CRZ)."""

import pytest
from fastapi.testclient import TestClient

from backend.adapters.api import project_config_api
from backend.adapters.persistence.project_config_store import ProjectConfigStore
from backend.server import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    store = ProjectConfigStore(tmp_path / "project_config.json")
    monkeypatch.setattr(project_config_api, "get_project_config_store", lambda *a, **k: store)
    return TestClient(app), store


def test_get_project_config_returns_null_when_not_saved(client):
    test_client, _ = client
    res = test_client.get("/project-config")
    assert res.status_code == 200
    assert res.json()["data"]["config"] is None


def test_save_and_get_project_config_roundtrip(client):
    test_client, _ = client
    body = {
        "project_name": "결제시스템 요구사항 관리",
        "goal": "요구사항 문서를 받아 영역별 태스크로 관리한다",
        "selected_areas": ["WEB", "SEC"],
        "actor": "pm@example.com",
    }
    res = test_client.put("/project-config", json=body)
    assert res.status_code == 200
    saved = res.json()["data"]["config"]
    assert saved["project_name"] == body["project_name"]
    assert saved["created_by"] == "pm@example.com"
    assert saved["created_at"]

    loaded = test_client.get("/project-config").json()["data"]["config"]
    assert loaded["project_name"] == body["project_name"]
    assert loaded["selected_areas"] == ["WEB", "SEC"]


def test_save_project_config_empty_areas_returns_422(client):
    test_client, _ = client
    res = test_client.put(
        "/project-config",
        json={"project_name": "x", "goal": "y", "actor": "tester"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AEGIS-VALIDATION"


def test_save_project_config_infra_policy_violation_returns_422(client):
    test_client, _ = client
    res = test_client.put(
        "/project-config",
        json={
            "project_name": "x",
            "goal": "y",
            "selected_areas": ["WEB"],
            "actor": "tester",
            "infra_configured": True,
            "infra_servers": [
                {"name": "db1", "zone": "external", "role": "DB", "ip": "1.2.3.4", "ports": [5432]}
            ],
        },
    )
    assert res.status_code == 422
    assert "외부 노출 존" in res.json()["error"]["message"]
