"""[2026-07-24 보안수정 회귀테스트] project_id/doc_id 경로 순회(CWE-22) 방지 확인.

5-agent 협업 진단(`plans/_plan/UPGRADE_PLAN_2026-07-24_5agent.md`)에서 실측 확인된
`project_scope.resolve_project_data_dir()`·`DocumentStore.save/load`의 경로 순회 취약점
수정을 검증한다 — ①저수준 함수가 안전 문자셋을 벗어난 값을 거부하는지 ②API 레벨에서
그 예외가 500(내부오류)이 아니라 400(AEGIS-VALIDATION)으로 응답되는지(T99 AIOS 경계검증)."""

import pytest
from fastapi.testclient import TestClient

from backend.adapters.persistence import project_scope
from backend.adapters.persistence.document_store import DocumentStore, InvalidDocIdError
from backend.adapters.persistence.project_scope import InvalidProjectIdError
from backend.server import app


@pytest.mark.parametrize("bad_project_id", ["../../etc", "..", "a/b", "a\\b", ""])
def test_resolve_project_data_dir_rejects_traversal(bad_project_id):
    with pytest.raises(InvalidProjectIdError):
        project_scope.resolve_project_data_dir(bad_project_id)


def test_resolve_project_data_dir_accepts_safe_ids():
    assert project_scope.resolve_project_data_dir("proj-001") is not None
    assert project_scope.resolve_project_data_dir("default") is not None


@pytest.mark.parametrize("bad_doc_id", ["../../etc/passwd", "..", "a/b", ""])
def test_document_store_rejects_traversal(tmp_path, bad_doc_id):
    store = DocumentStore(tmp_path)
    with pytest.raises(InvalidDocIdError):
        store.save(bad_doc_id, "content")
    with pytest.raises(InvalidDocIdError):
        store.load(bad_doc_id)


def test_document_store_accepts_safe_doc_id(tmp_path):
    store = DocumentStore(tmp_path)
    store.save("doc-abc123", "hello")
    assert store.load("doc-abc123") == "hello"


@pytest.fixture
def client():
    return TestClient(app)


def test_api_rejects_path_traversal_project_id_with_400(client):
    resp = client.get("/requirements", params={"project_id": "../../etc"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "AEGIS-VALIDATION"


def test_api_rejects_path_traversal_doc_id_with_400(client):
    resp = client.get("/documents/../../etc/chunk-map", params={"actor": "tester"})
    # doc_id가 라우트 경로 세그먼트라 매칭 자체가 안 될 수도 있으나(404), 매칭되면
    # 400이어야 한다 — 어느 쪽이든 500(내부오류 노출)이면 실패.
    assert resp.status_code in (400, 404)
