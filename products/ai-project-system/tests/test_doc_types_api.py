"""문서유형 동적 추가 API(doc_types_api.py) — projects_api 테스트와 동일 패턴(CRZ)."""

import pytest
from fastapi.testclient import TestClient

from backend.adapters.api import doc_types_api
from backend.adapters.persistence.doc_type_registry import DocTypeRegistry
from backend.domain.requirements.codes import DOC_TYPE_CODES
from backend.server import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    registry = DocTypeRegistry(tmp_path / "doc_types.json")
    monkeypatch.setattr(doc_types_api, "get_doc_type_registry", lambda *a, **k: registry)
    return TestClient(app), registry


def test_list_doc_types_includes_builtins(client):
    test_client, _ = client
    res = test_client.get("/doc-types")
    assert res.status_code == 200
    body = res.json()
    codes = {d["code"] for d in body["data"]["doc_types"]}
    assert set(DOC_TYPE_CODES).issubset(codes)
    assert all(not d["custom"] for d in body["data"]["doc_types"] if d["code"] in DOC_TYPE_CODES)


def test_create_doc_type_success(client):
    test_client, _ = client
    res = test_client.post("/doc-types", json={"label": "회의록", "actor": "tester"})
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["custom"] is True
    assert body["data"]["label"] == "회의록"

    listed = test_client.get("/doc-types").json()
    codes = {d["code"]: d for d in listed["data"]["doc_types"]}
    assert body["data"]["code"] in codes
    assert codes[body["data"]["code"]]["custom"] is True


def test_create_doc_type_empty_label_returns_422(client):
    test_client, _ = client
    res = test_client.post("/doc-types", json={"label": "  ", "actor": "tester"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AEGIS-VALIDATION"


def test_create_doc_type_duplicate_builtin_code_returns_422(client):
    test_client, _ = client
    res = test_client.post("/doc-types", json={"label": "x", "actor": "tester", "code": "BIZ"})
    assert res.status_code == 422
