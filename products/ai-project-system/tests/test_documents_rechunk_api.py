"""POST /documents/{doc_id}/rechunk -- 202+job_id+polling conversion test file (2026-07-27)."""

import io

import pytest
from fastapi.testclient import TestClient

from backend.adapters.api import documents_api, requirements_api
from backend.adapters.persistence.document_store import DocumentStore
from backend.adapters.persistence.requirement_store import RequirementStore
from backend.server import app
from tests._job_polling import poll_job_until_done


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
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["data"]["job_id"]
    body = poll_job_until_done(test_client, job_id)
    assert body["data"]["status"] == "done", body
    return body["data"]["result"]


def test_rechunk_withdraws_old_and_creates_new(client):
    test_client, req_store, doc_store = client
    upload_data = _upload_sample(test_client)
    doc_id = upload_data["doc_id"]
    original_req_ids = set(upload_data["requirements_created"])
    assert original_req_ids, "no requirements created from upload -- test precondition violated"

    resp = test_client.post(
        f"/documents/{doc_id}/rechunk",
        json={"actor": "tester2", "reason": "chunk boundary cut mid-sentence"},
    )
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["data"]["job_id"]
    body = poll_job_until_done(test_client, job_id)

    assert body["ok"] is True
    assert body["data"]["status"] == "done"
    data = body["data"]["result"]
    assert data["doc_id"] == doc_id
    assert set(data["withdrawn_req_ids"]) == original_req_ids
    assert data["requirements_created"], "rechunk created no new requirements"

    all_records = {r.req_id: r for r in req_store.list_all()}
    for old_id in original_req_ids:
        assert all_records[old_id].lifecycle_status == "WITHDRAWN"
        assert "[RECHUNK]" in all_records[old_id].status_history[-1]["reason"]

    new_ids = set(data["requirements_created"])
    assert new_ids.isdisjoint(original_req_ids)
    for new_id in new_ids:
        assert all_records[new_id].doc_id == doc_id
        assert all_records[new_id].lifecycle_status != "WITHDRAWN"

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
