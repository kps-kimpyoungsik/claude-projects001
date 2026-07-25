"""요구사항 상태변경/미리보기 API — FastAPI TestClient로 인메모리 검증(실서버 기동 없음).

`backend.adapters.api.requirements_api`가 `get_requirement_store()`/`get_document_store()`
로 스토어를 얻으므로, 테스트에서는 FastAPI dependency_overrides 대신 monkeypatch로 이
두 팩토리를 tmp_path 기반 스토어로 바꿔치기한다(라우터 코드 수정 없이 격리).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.adapters.api import requirements_api
from backend.adapters.persistence.document_store import DocumentStore
from backend.adapters.persistence.requirement_store import RequirementStore
from backend.adapters.persistence.task_store import TaskStore
from backend.domain.requirements.classifier import classify_chunk
from backend.server import app

SECURITY_TEXT = "# 보안 요건\n암호화 솔루션과 SSL 인증서를 적용하고 소스코드 취약성 점검을 수행한다."


@pytest.fixture
def client(tmp_path, monkeypatch):
    req_store = RequirementStore(tmp_path / "requirements_store.json")
    doc_store = DocumentStore(tmp_path / "documents")
    task_store = TaskStore(tmp_path / "tasks_store.json")
    access_log = tmp_path / "preview_access_log.jsonl"
    graph_path = tmp_path / ".graphify-out" / "graph.json"

    monkeypatch.setattr(requirements_api, "get_requirement_store", lambda *a, **k: req_store)
    monkeypatch.setattr(requirements_api, "get_document_store", lambda *a, **k: doc_store)
    monkeypatch.setattr(requirements_api, "_get_task_store_for_generation", lambda *a, **k: task_store)
    monkeypatch.setattr(requirements_api, "_preview_access_log_path", lambda *a, **k: access_log)
    # [2026-07-25 회귀수정] sync_requirement_to_graph()가 _graph_path()로 그래프 경로를 얻는다
    # (다른 팩토리와 동일 격리 원칙, CRZ) — 격리 없으면 실제 data/.graphify-out/graph.json을
    # 오염시켜 다른 테스트(e2e 등)가 그 잔재를 읽고 오판정한다(tests/test_e2e_task_lifecycle.py
    # 회귀 사례와 동일 근본원인 — plans/_plan/UPGRADE_PLAN_2026-07-24_5agent.md 2026-07-25 기록 참조).
    monkeypatch.setattr(requirements_api, "_graph_path", lambda *a, **k: graph_path)

    return TestClient(app), req_store, doc_store


def _make_record(req_store, doc_store, doc_id="doc1"):
    classification = classify_chunk(SECURITY_TEXT)
    content = "머리말\n\n# 보안 요건\n암호화 솔루션과 SSL 인증서를 적용한다.\n"
    doc_store.save(doc_id, content)
    char_start = content.index("암호화")
    char_end = char_start + len("암호화 솔루션과 SSL 인증서를 적용한다.")
    record = req_store.add_from_classification(
        classification,
        description="보안 요건",
        source_ref="doc::child:0",
        doc_id=doc_id,
        heading_path=["보안 요건"],
        char_start=char_start,
        char_end=char_end,
    )
    assert record is not None
    return record


def test_status_change_success(client):
    http, req_store, doc_store = client
    record = _make_record(req_store, doc_store)

    res = http.post(
        f"/requirements/{record.req_id}/status",
        json={"status": "ACCEPTED", "actor": "hong.gildong"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["lifecycle_status"] == "ACCEPTED"
    assert body["error"] is None
    assert body["meta"] == {"degraded": False, "stub": False}


def test_status_change_unknown_req_id_returns_4xx(client):
    http, _, _ = client
    res = http.post(
        "/requirements/REQ-QA-SEC-999/status",
        json={"status": "ACCEPTED", "actor": "hong.gildong"},
    )
    assert res.status_code == 404
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "AEGIS-NOTFOUND"


def test_status_change_missing_reason_for_withdrawn_returns_4xx(client):
    http, req_store, doc_store = client
    record = _make_record(req_store, doc_store)

    res = http.post(
        f"/requirements/{record.req_id}/status",
        json={"status": "WITHDRAWN", "actor": "hong.gildong"},
    )
    assert res.status_code == 422
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "AEGIS-VALIDATION"


def test_status_change_malformed_body_returns_4xx(client):
    http, req_store, doc_store = client
    record = _make_record(req_store, doc_store)

    # actor 누락 — Pydantic 422 (T99 AIOS 경계검증, 별도 코드 없이 충족).
    res = http.post(f"/requirements/{record.req_id}/status", json={"status": "ACCEPTED"})
    assert res.status_code == 422


def test_preview_returns_excerpt(client):
    http, req_store, doc_store = client
    record = _make_record(req_store, doc_store)

    res = http.get(f"/requirements/{record.req_id}/preview", params={"actor": "hong.gildong"})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["content_excerpt"] == "암호화 솔루션과 SSL 인증서를 적용한다."
    assert body["data"]["heading_path"] == ["보안 요건"]


def test_preview_unknown_req_id_returns_4xx(client):
    http, _, _ = client
    res = http.get("/requirements/REQ-QA-SEC-999/preview", params={"actor": "hong.gildong"})
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "AEGIS-NOTFOUND"


def test_preview_pii_gate_excludes_content_without_confirmation(client, monkeypatch):
    """실제 pii_detector.scan_for_pii()가 이제 contains_pii를 채우므로(2026-07-19 활성화),
    동적 속성 부여가 아니라 실제 PII 문구가 포함된 요구사항으로 게이트 자체를 검증한다."""
    http, req_store, doc_store = client
    doc_id = "doc-pii"
    classification = classify_chunk(SECURITY_TEXT)
    content = "머리말\n\n# 보안 요건\n담당자 연락처는 010-1234-5678, 이메일은 a@b.com 이다.\n"
    doc_store.save(doc_id, content)
    char_start = content.index("담당자")
    char_end = char_start + len("담당자 연락처는 010-1234-5678, 이메일은 a@b.com 이다.")
    record = req_store.add_from_classification(
        classification,
        description="담당자 연락처는 010-1234-5678, 이메일은 a@b.com 이다.",
        source_ref="doc::child:0",
        doc_id=doc_id,
        heading_path=["보안 요건"],
        char_start=char_start,
        char_end=char_end,
    )
    assert record.contains_pii is True

    res = http.get(f"/requirements/{record.req_id}/preview", params={"actor": "hong.gildong", "confirm_pii": "false"})
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["requires_pii_confirmation"] is True
    assert "content_excerpt" not in body["data"]

    res2 = http.get(f"/requirements/{record.req_id}/preview", params={"actor": "hong.gildong", "confirm_pii": "true"})
    body2 = res2.json()
    assert body2["data"]["content_excerpt"] is not None


def test_preview_non_pii_record_has_contains_pii_false(client):
    """PII 문구가 없는 일반 요구사항은 contains_pii=False로 실제 판정돼야 한다(§DRL-2 활성화 이후
    회귀 확인 — 이전엔 필드 자체가 없어 게이트가 사실상 no-op이었다)."""
    http, req_store, doc_store = client
    record = _make_record(req_store, doc_store)

    assert record.contains_pii is False

    res = http.get(f"/requirements/{record.req_id}/preview", params={"actor": "hong.gildong"})
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["contains_pii"] is False
    assert body["data"]["content_excerpt"] is not None


def test_rechunk_success(client):
    http, req_store, doc_store = client
    record = _make_record(req_store, doc_store)

    res = http.post(
        f"/requirements/{record.req_id}/rechunk",
        json={"actor": "hong.gildong", "reason": "청킹 경계가 문장 중간에서 잘림", "suggested_char_start": 5, "suggested_char_end": 20},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["lifecycle_status"] == "REJECTED"
    assert body["data"]["status_history"][-1]["reason"] == "[RECHUNK] 청킹 경계가 문장 중간에서 잘림"


def test_rechunk_unknown_req_id_returns_4xx(client):
    http, _, _ = client
    res = http.post(
        "/requirements/REQ-QA-SEC-999/rechunk",
        json={"actor": "hong.gildong", "reason": "x"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "AEGIS-NOTFOUND"


def test_rechunk_missing_reason_returns_4xx(client):
    http, req_store, doc_store = client
    record = _make_record(req_store, doc_store)

    res = http.post(f"/requirements/{record.req_id}/rechunk", json={"actor": "hong.gildong"})
    assert res.status_code == 422


def test_list_requirements_includes_work_status_fields(client):
    http, req_store, doc_store = client
    record = _make_record(req_store, doc_store)

    res = http.get("/requirements")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    items = body["data"]["requirements"]
    assert len(items) == 1
    assert items[0]["req_id"] == record.req_id
    assert items[0]["work_status"] == "NOT_DISPATCHED"
    assert items[0]["assigned_agent_command"] is None


def test_get_requirement_by_id_includes_new_fields(client):
    http, req_store, doc_store = client
    record = _make_record(req_store, doc_store)
    req_store.set_work_status(record.req_id, "IN_PROGRESS", "/aegis-security")

    res = http.get(f"/requirements/{record.req_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["work_status"] == "IN_PROGRESS"
    assert body["data"]["assigned_agent_command"] == "/aegis-security"


def test_get_requirement_unknown_id_returns_4xx(client):
    http, _, _ = client
    res = http.get("/requirements/REQ-QA-SEC-999")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "AEGIS-NOTFOUND"


def test_preview_missing_contains_pii_field_defaults_to_no_gate(client):
    """구버전 스토어 파일(필드 없는 레코드)과의 호환 — getattr 기본값 폴백이 여전히 동작해야
    한다. 실제 record 객체에서 속성을 지워 "필드가 아예 없는" 상태를 시뮬레이션한다."""
    http, req_store, doc_store = client
    record = _make_record(req_store, doc_store)

    records = {r.req_id: r for r in req_store.list_all()}
    target = records[record.req_id]
    del target.contains_pii  # 구버전 레코드 시뮬레이션 — 필드 자체가 없는 상태.

    def fake_list_all():
        return [target]

    monkeypatch_target = req_store
    monkeypatch_target.list_all = fake_list_all

    res = http.get(f"/requirements/{record.req_id}/preview", params={"actor": "hong.gildong"})
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["contains_pii"] is False
    assert body["data"]["content_excerpt"] is not None


def test_generate_task_creates_draft_task_referencing_requirement(client):
    """[2026-07-23 신규] REQ→Task 뼈대 생성 — 실측 검토에서 발견된 Critical 갭 해소.
    acceptance_criteria/impact_scope/solution_stack 없이 생성되므로 충분성 체크에 걸려
    needs_escalation=True + status=DRAFT로 묶여야 한다(자동생성≠즉시실행가능)."""
    http, req_store, doc_store = client
    record = _make_record(req_store, doc_store)

    res = http.post(f"/requirements/{record.req_id}/generate-task")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["domain_code"] == record.area_code
    assert data["source_req_ids"] == [record.req_id]
    assert data["status"] == "DRAFT"
    assert data["needs_escalation"] is True
    assert data["already_existed"] is False
    assert data["task_id"].startswith(f"TASK-{record.area_code}-")


def test_generate_task_is_idempotent_on_repeat_call(client):
    """같은 REQ에 재호출해도 Task가 중복 생성되지 않고 기존 Task를 그대로 반환해야 한다."""
    http, req_store, doc_store = client
    record = _make_record(req_store, doc_store)

    first = http.post(f"/requirements/{record.req_id}/generate-task").json()
    second = http.post(f"/requirements/{record.req_id}/generate-task").json()

    assert first["data"]["already_existed"] is False
    assert second["data"]["already_existed"] is True
    assert second["data"]["task_id"] == first["data"]["task_id"]

    task_store = requirements_api._get_task_store_for_generation(project_id="default")
    assert len(task_store.list_all()) == 1


def test_generate_task_unknown_req_id_returns_404(client):
    http, _, _ = client
    res = http.post("/requirements/REQ-QA-SEC-999/generate-task")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "AEGIS-NOTFOUND"


def test_generate_task_rejects_rejected_requirement(client):
    http, req_store, doc_store = client
    record = _make_record(req_store, doc_store)
    req_store.set_status(record.req_id, "REJECTED", actor="hong.gildong", reason="중복 요건")

    res = http.post(f"/requirements/{record.req_id}/generate-task")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AEGIS-VALIDATION"
