"""POST /documents/{doc_id}/rechunk — 실제 재청킹 실행기 테스트(2026-07-26 신규).

기존 `POST /requirements/{req_id}/rechunk`("재청킹 요청")는 이름과 달리 청킹을 재실행하지
않고 REQ 1건을 REJECTED로 표시만 했다(실측 확인 갭). 이 테스트는 새로 만든 문서 단위
재청킹 실행기가 실제로 (1) 기존 REQ를 WITHDRAWN 처리하고 (2) 저장된 원문을 다시 청킹해
새 REQ를 채번하는지 검증한다. fixture는 test_documents_upload_api.py와 동일한 monkeypatch
격리 패턴을 재사용한다(신규 로직 없음, CRZ).
"""

import io

import pytest
from fastapi.testclient import TestClient

from backend.adapters.api import documents_api, requirements_api
from backend.adapters.persistence.document_store import DocumentStore
from backend.adapters.persistence.requirement_store import RequirementStore
from backend.server import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    req_store = RequirementStore(tmp_path / "requirements_store.json")
    doc_store = DocumentStore(tmp_path / "documents")
    graph_path = tmp_path / ".graphify-out" / "graph.json"
    monkeypatch.setattr(requirements_api, "get_requirement_store", lambda *a, **k: req_store)
    monkeypatch.setattr(requirements_api, "get_document_store", lambda *a, **k: doc_store)
    monkeypatch.setattr(requirements_api, "_graph_path", lambda *a, **k: graph_path)
    monkeypatch.setattr(documents_api.project_scope, "resolve_project_data_dir", lambda *a, **k: tmp_path)
    return TestClient(app), req_store, doc_store


def _upload_sample(test_client):
    content = (
        b"# Security Requirements\n"
        b"Encryption and SSL certificates must be applied.\n\n"
        b"# Performance Requirements\n"
        b"Response time must be under 200ms.\n"
    )
    resp = test_client.post(
        "/documents/upload",
        files={"file": ("sample.txt", io.BytesIO(content), "text/plain")},
        data={"actor": "tester"},
    )
    assert resp.status_code == 200
    return resp.json()["data"]


def test_rechunk_withdraws_old_and_creates_new(client):
    test_client, req_store, doc_store = client
    upload_data = _upload_sample(test_client)
    doc_id = upload_data["doc_id"]
    original_req_ids = set(upload_data["requirements_created"])
    assert original_req_ids, "업로드에서 요구사항이 하나도 생성되지 않음 — 테스트 전제 위반"

    resp = test_client.post(
        f"/documents/{doc_id}/rechunk",
        json={"actor": "tester2", "reason": "청킹 경계가 문장 중간에서 잘림"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["doc_id"] == doc_id
    assert set(data["withdrawn_req_ids"]) == original_req_ids
    assert data["requirements_created"], "재청킹으로 새 REQ가 하나도 생성되지 않음"

    # 옛 REQ는 물리 삭제가 아니라 WITHDRAWN으로 남아있어야 한다(감사 이력 보존).
    all_records = {r.req_id: r for r in req_store.list_all()}
    for old_id in original_req_ids:
        assert all_records[old_id].lifecycle_status == "WITHDRAWN"
        assert "[RECHUNK]" in all_records[old_id].status_history[-1]["reason"]

    # 새 REQ는 이 문서에서 나온 것으로 기록되고 옛 REQ와 겹치지 않는 새 ID다.
    new_ids = set(data["requirements_created"])
    assert new_ids.isdisjoint(original_req_ids)
    for new_id in new_ids:
        assert all_records[new_id].doc_id == doc_id
        assert all_records[new_id].lifecycle_status != "WITHDRAWN"

    # 원문은 그대로 보존돼야 한다(재청킹이 원문 자체를 훼손하지 않음).
    assert doc_store.load(doc_id) is not None


def test_rechunk_missing_doc_id_returns_404(client):
    test_client, _req_store, _doc_store = client
    resp = test_client.post(
        "/documents/doc-nonexistent000/rechunk",
        json={"actor": "tester", "reason": "no such doc"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "AEGIS-NOTFOUND"


def test_rechunk_requires_reason_and_actor(client):
    test_client, _req_store, _doc_store = client
    upload_data = _upload_sample(test_client)
    doc_id = upload_data["doc_id"]

    resp = test_client.post(f"/documents/{doc_id}/rechunk", json={"actor": "tester", "reason": ""})
    assert resp.status_code == 422

    resp2 = test_client.post(f"/documents/{doc_id}/rechunk", json={"actor": "", "reason": "why"})
    assert resp2.status_code == 422
