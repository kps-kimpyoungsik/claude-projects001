"""문서 전체 청크맵 API(§6) — FastAPI TestClient로 인메모리 검증(실서버 기동 없음).

`backend.adapters.api.documents_api`가 `requirements_api.get_requirement_store()`/
`get_document_store()`를 모듈 참조로 호출하므로, tests/test_requirements_api.py와 동일한
monkeypatch 격리 패턴을 그대로 재사용한다(신규 fixture 로직 없음, CRZ).
"""

import pytest
from fastapi.testclient import TestClient

from backend.adapters.api import requirements_api
from backend.adapters.persistence.document_store import DocumentStore
from backend.adapters.persistence.requirement_store import RequirementStore
from backend.domain.requirements.classifier import classify_chunk
from backend.server import app

SECURITY_TEXT = "# 보안 요건\n암호화 솔루션과 SSL 인증서를 적용하고 소스코드 취약성 점검을 수행한다."


@pytest.fixture
def client(tmp_path, monkeypatch):
    req_store = RequirementStore(tmp_path / "requirements_store.json")
    doc_store = DocumentStore(tmp_path / "documents")
    access_log = tmp_path / "preview_access_log.jsonl"
    graph_path = tmp_path / ".graphify-out" / "graph.json"

    monkeypatch.setattr(requirements_api, "get_requirement_store", lambda *a, **k: req_store)
    monkeypatch.setattr(requirements_api, "get_document_store", lambda *a, **k: doc_store)
    monkeypatch.setattr(requirements_api, "_preview_access_log_path", lambda *a, **k: access_log)
    # [2026-07-25 회귀수정] _graph_path() 격리(tests/test_requirements_api.py와 동일 패턴) —
    # 없으면 실제 data/.graphify-out/graph.json 오염(CRZ).
    monkeypatch.setattr(requirements_api, "_graph_path", lambda *a, **k: graph_path)

    return TestClient(app), req_store, doc_store


def _make_record(req_store, doc_store, doc_id, description, char_start, char_end):
    classification = classify_chunk(SECURITY_TEXT)
    record = req_store.add_from_classification(
        classification,
        description=description,
        source_ref="doc::child:0",
        doc_id=doc_id,
        heading_path=["보안 요건"],
        char_start=char_start,
        char_end=char_end,
    )
    assert record is not None
    return record


def test_chunk_map_returns_content_and_sorted_chunks(client):
    http, req_store, doc_store = client
    doc_id = "doc1"
    content = "머리말\n\n# 보안 요건\n암호화 솔루션과 SSL 인증서를 적용한다.\n추가 문구입니다.\n"
    doc_store.save(doc_id, content)

    second_start = content.index("추가")
    second_end = second_start + len("추가 문구입니다.")
    first_start = content.index("암호화")
    first_end = first_start + len("암호화 솔루션과 SSL 인증서를 적용한다.")

    # 일부러 뒤쪽 구간부터 만들어 정렬 검증(char_start 오름차순으로 응답돼야 함).
    _make_record(req_store, doc_store, doc_id, "추가 문구", second_start, second_end)
    _make_record(req_store, doc_store, doc_id, "보안 요건", first_start, first_end)

    res = http.get(f"/documents/{doc_id}/chunk-map", params={"actor": "hong.gildong"})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["content"] == content
    assert body["data"]["requires_pii_confirmation"] is False
    chunks = body["data"]["chunks"]
    assert len(chunks) == 2
    assert chunks[0]["char_start"] == first_start
    assert chunks[1]["char_start"] == second_start
    assert chunks[0]["area_code"]


def test_chunk_map_unknown_doc_id_returns_404(client):
    http, _, _ = client
    res = http.get("/documents/does-not-exist/chunk-map", params={"actor": "hong.gildong"})
    assert res.status_code == 404
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "AEGIS-NOTFOUND"


def test_chunk_map_no_chunks_returns_empty_list(client):
    http, req_store, doc_store = client
    doc_id = "doc-empty"
    doc_store.save(doc_id, "아무도 청킹하지 않은 문서입니다.")

    res = http.get(f"/documents/{doc_id}/chunk-map", params={"actor": "hong.gildong"})
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["chunks"] == []
    assert body["data"]["content"]


def test_chunk_map_pii_gate_blocks_content_without_confirmation(client):
    http, req_store, doc_store = client
    doc_id = "doc-pii"
    content = "머리말\n\n# 보안 요건\n담당자 연락처는 010-1234-5678, 이메일은 a@b.com 이다.\n"
    doc_store.save(doc_id, content)
    char_start = content.index("담당자")
    char_end = char_start + len("담당자 연락처는 010-1234-5678, 이메일은 a@b.com 이다.")
    record = _make_record(
        req_store, doc_store, doc_id,
        "담당자 연락처는 010-1234-5678, 이메일은 a@b.com 이다.", char_start, char_end,
    )
    assert record.contains_pii is True

    res = http.get(f"/documents/{doc_id}/chunk-map", params={"actor": "hong.gildong"})
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["requires_pii_confirmation"] is True
    assert "content" not in body["data"]

    res2 = http.get(
        f"/documents/{doc_id}/chunk-map",
        params={"actor": "hong.gildong", "confirm_pii": "true"},
    )
    body2 = res2.json()
    assert body2["data"]["requires_pii_confirmation"] is False
    assert body2["data"]["content"] == content
