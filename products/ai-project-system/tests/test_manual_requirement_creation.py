"""[2026-07-23 고도화] "단건 요구사항 등록"(POST /requirements) — 문서 업로드 없이 사람이
직접 입력한 요구사항 1건을 즉시 채번하는 경로 검증. 사용자 지시: "중간 애자일 방식
요구사항이 들어올 수도 있고... 단건 등록 프롬프트가 될 수도 있어서"에 대한 실제 구현.

`project_scope.resolve_project_data_dir()`를 tmp_path로 바꿔치기(test_project_scoped_
isolation.py와 동일 패턴, CRZ)해 실제 HTTP 요청으로 검증한다."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.adapters.persistence import project_scope
from backend.server import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    def _scoped_dir(project_id: str) -> Path:
        return tmp_path / project_id

    monkeypatch.setattr(project_scope, "resolve_project_data_dir", _scoped_dir)
    return TestClient(app)


def test_manual_requirement_creation_success(client):
    res = client.post(
        "/requirements",
        params={"project_id": "proj-x"},
        json={
            "description": "회의 중 나온 긴급 요청 — 로그인 화면에 소셜로그인 버튼 추가",
            "doc_type_code": "BIZ",
            "area_code": "WEB",
            "actor": "tester",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["req_id"].startswith("REQ-BIZ-WEB-")
    assert body["data"]["lifecycle_status"] == "CLASSIFIED"  # needs_review=False라 즉시 확정
    assert body["data"]["source_ref"] == "manual::tester"

    listed = client.get("/requirements", params={"project_id": "proj-x"}).json()
    assert body["data"]["req_id"] in [r["req_id"] for r in listed["data"]["requirements"]]


def test_manual_requirement_creation_with_custom_doc_type(client):
    created_type = client.post(
        "/doc-types", params={"project_id": "proj-y"}, json={"label": "회의록", "actor": "tester"}
    ).json()
    custom_code = created_type["data"]["code"]

    res = client.post(
        "/requirements",
        params={"project_id": "proj-y"},
        json={
            "description": "회의록에서 추출한 요청사항",
            "doc_type_code": custom_code,
            "area_code": "WAS",
            "actor": "tester",
        },
    )
    assert res.status_code == 200
    assert res.json()["data"]["req_id"].startswith(f"REQ-{custom_code}-WAS-")


def test_manual_requirement_creation_unknown_doc_type_returns_422(client):
    res = client.post(
        "/requirements",
        params={"project_id": "proj-z"},
        json={"description": "설명", "doc_type_code": "ZZZ", "area_code": "WEB", "actor": "tester"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AEGIS-VALIDATION"


def test_manual_requirement_creation_unknown_area_code_returns_422(client):
    res = client.post(
        "/requirements",
        params={"project_id": "proj-z"},
        json={"description": "설명", "doc_type_code": "BIZ", "area_code": "ZZZ", "actor": "tester"},
    )
    assert res.status_code == 422


def test_manual_requirement_creation_missing_required_field_returns_422(client):
    res = client.post(
        "/requirements",
        params={"project_id": "proj-z"},
        json={"description": "설명", "doc_type_code": "BIZ", "actor": "tester"},
    )
    assert res.status_code == 422
