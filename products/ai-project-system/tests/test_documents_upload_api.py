"""POST /documents/upload — 실제 HTTP 업로드 엔드포인트 테스트(2026-07-22 신규).

`document_upload_service.process_uploaded_file`이 테스트에서만 직접 호출되고 실제
라우트가 없었던 갭을 메운 배선을 검증한다. fixture는 test_documents_api.py와 동일한
monkeypatch 격리 패턴을 재사용한다(신규 로직 없음, CRZ).
"""

import io

import pytest
from fastapi.testclient import TestClient

from backend.adapters.api import requirements_api
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
    # [2026-07-25 회귀수정] 문서업로드→요구사항 채번 경로가 sync_requirement_to_graph()를
    # 거쳐 _graph_path()에 쓴다 — 격리 없으면 실제 data/.graphify-out/graph.json 오염(CRZ,
    # tests/test_requirements_api.py와 동일 패턴).
    monkeypatch.setattr(requirements_api, "_graph_path", lambda *a, **k: graph_path)
    return TestClient(app), req_store, doc_store


def test_upload_txt_document_creates_chunks(client):
    test_client, req_store, doc_store = client
    content = b"# Security Requirements\nEncryption and SSL certificates must be applied."

    resp = test_client.post(
        "/documents/upload",
        files={"file": ("sample.txt", io.BytesIO(content), "text/plain")},
        data={"actor": "tester"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["doc_filename"] == "sample.txt"
    assert body["data"]["chunk_count"] >= 1
    assert doc_store.load(body["data"]["doc_id"]) is not None


def test_upload_empty_file_returns_422(client):
    test_client, _, _ = client
    resp = test_client.post(
        "/documents/upload",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
        data={"actor": "tester"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "AEGIS-VALIDATION"


def test_upload_unsupported_extension_returns_422(client):
    test_client, _, _ = client
    resp = test_client.post(
        "/documents/upload",
        files={"file": ("file.xyz", io.BytesIO(b"content"), "application/octet-stream")},
        data={"actor": "tester"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "AEGIS-VALIDATION"


def test_upload_not_yet_implemented_format_returns_422(client):
    test_client, _, _ = client
    # .hwp는 FORMAT_STRATEGY에는 있으나 실제 어댑터가 아직 없다(HWP 파서 미구현)
    resp = test_client.post(
        "/documents/upload",
        files={"file": ("doc.hwp", io.BytesIO(b"fake hwp content"), "application/octet-stream")},
        data={"actor": "tester"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "AEGIS-VALIDATION"
