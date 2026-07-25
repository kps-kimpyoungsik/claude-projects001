"""요구사항 저장소 — REQ 채번·라이프사이클 상태전이·감사로그 회귀 테스트."""

import pytest

from backend.domain.requirements.classifier import classify_chunk
from backend.adapters.persistence.requirement_store import RequirementStore


@pytest.fixture
def store(tmp_path):
    return RequirementStore(tmp_path / "requirements_store.json")


SECURITY_TEXT = "# 보안 요건\n암호화 솔루션과 SSL 인증서를 적용하고 소스코드 취약성 점검을 수행한다."


def test_add_from_classification_creates_req_id(store):
    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0")
    assert record is not None
    assert record.req_id.startswith("REQ-QA-SEC-")
    assert record.lifecycle_status in {"CLASSIFIED", "UNDER_REVIEW"}


def test_add_from_classification_returns_none_without_doc_type_or_area(store):
    classification = classify_chunk("특별한 키워드가 없는 문장.")
    record = store.add_from_classification(classification, description="x", source_ref="doc::child:1")
    assert record is None


def test_set_status_requires_reason_for_withdrawn_and_rejected(store):
    classification = classify_chunk("암호화 솔루션과 SSL 인증서를 적용한다.")
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0")

    with pytest.raises(ValueError):
        store.set_status(record.req_id, "WITHDRAWN", actor="pm@example.com")

    updated = store.set_status(record.req_id, "WITHDRAWN", actor="pm@example.com", reason="요구사항 변경")
    assert updated.lifecycle_status == "WITHDRAWN"
    assert len(updated.status_history) == 1
    assert updated.status_history[0]["actor"] == "pm@example.com"
    assert updated.status_history[0]["reason"] == "요구사항 변경"


def test_set_status_rejects_unknown_status(store):
    classification = classify_chunk("암호화 솔루션과 SSL 인증서를 적용한다.")
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0")
    with pytest.raises(ValueError):
        store.set_status(record.req_id, "NOT_A_REAL_STATUS", actor="pm")


def test_sequential_seq_numbers_within_same_doc_area(store):
    classification = classify_chunk("암호화 솔루션과 SSL 인증서를 적용한다.")
    r1 = store.add_from_classification(classification, description="a", source_ref="doc::child:0")
    r2 = store.add_from_classification(classification, description="b", source_ref="doc::child:1")
    assert r1.req_id != r2.req_id


def test_add_from_classification_detects_pii_in_description(store):
    """§DRL-2 — contains_pii가 pii_detector.scan_for_pii()로 실제 채워져야 한다."""
    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(
        classification,
        description="담당자 연락처는 010-1234-5678이고 이메일은 pm@example.com 이다.",
        source_ref="doc::child:0",
    )
    assert record.contains_pii is True
    assert any(m.startswith("pattern:PHONE") for m in record.pii_scan_matched)
    assert any(m.startswith("pattern:EMAIL") for m in record.pii_scan_matched)


def test_add_from_classification_no_pii_in_plain_description(store):
    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0")
    assert record.contains_pii is False
    assert record.pii_scan_matched == []


def test_add_from_classification_derives_doc_filename(store):
    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(
        classification, description="보안 요건", source_ref="doc::child:0", doc_id="doc1",
    )
    assert record.doc_filename == "doc1.md"

    record_no_doc = store.add_from_classification(
        classification, description="보안 요건", source_ref="doc::child:1",
    )
    assert record_no_doc.doc_filename is None


def test_set_design_draft_gate_updates_value_and_records_history(store):
    """plans/_plan/01_PHASE1_DATA_MODEL.md §2-7 — 수동 override + 이력 기록."""
    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0")

    updated = store.set_design_draft_gate(
        record.req_id, "MANDATORY", actor="pm@example.com", reason="화면 확인 필요",
    )
    assert updated.design_draft_gate == "MANDATORY"
    assert updated.design_draft_gate_confidence == 1.0
    assert len(updated.design_draft_gate_history) == 1
    assert updated.design_draft_gate_history[0]["actor"] == "pm@example.com"
    assert updated.design_draft_gate_history[0]["reason"] == "화면 확인 필요"
    assert updated.design_draft_gate_history[0]["to_status"] == "MANDATORY"


def test_set_design_draft_gate_does_not_require_reason(store):
    """§2-7 — WITHDRAWN/REJECTED와 달리 이 필드는 reason을 강제하지 않는다."""
    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0")

    updated = store.set_design_draft_gate(record.req_id, "NOT_MANDATORY", actor="system")
    assert updated.design_draft_gate == "NOT_MANDATORY"
    assert updated.design_draft_gate_history[0]["reason"] is None


def test_set_design_draft_gate_rejects_unknown_value(store):
    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0")
    with pytest.raises(ValueError):
        store.set_design_draft_gate(record.req_id, "NOT_A_REAL_GATE_VALUE", actor="pm")


def test_request_rechunk_sets_rejected_with_prefixed_reason_and_appends_queue(store, tmp_path):
    """02_PHASE2_ORCHESTRATION_PREVIEW.md §5-2 — REJECTED 재사용 + rechunk_queue.jsonl append."""
    import json as _json

    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0", doc_id="doc1")

    updated = store.request_rechunk(
        record.req_id, actor="pm@example.com", reason="두 요구사항이 한 청크로 합쳐짐",
        suggested_char_start=10, suggested_char_end=40,
    )
    assert updated.lifecycle_status == "REJECTED"
    assert updated.status_history[-1]["reason"] == "[RECHUNK] 두 요구사항이 한 청크로 합쳐짐"

    queue_path = tmp_path / "rechunk_queue.jsonl"
    assert queue_path.exists()
    lines = queue_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = _json.loads(lines[0])
    assert entry["req_id"] == record.req_id
    assert entry["doc_id"] == "doc1"
    assert entry["actor"] == "pm@example.com"
    assert entry["suggested_char_start"] == 10
    assert entry["suggested_char_end"] == 40


def test_request_rechunk_unknown_req_id_raises(store):
    with pytest.raises(KeyError):
        store.request_rechunk("REQ-QA-SEC-999", actor="pm", reason="x")


def test_set_work_status_updates_fields(store):
    """06_AGENT_DISPATCH_REPORTING.md §10-2/§10-3 — 배차 결과 되먹임."""
    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0")
    assert record.work_status == "NOT_DISPATCHED"
    assert record.assigned_agent_command is None

    updated = store.set_work_status(record.req_id, "IN_PROGRESS", "/aegis-security")
    assert updated.work_status == "IN_PROGRESS"
    assert updated.assigned_agent_command == "/aegis-security"
    assert updated.work_status_updated_at != ""


def test_set_work_status_rejects_unknown_value(store):
    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0")
    with pytest.raises(ValueError):
        store.set_work_status(record.req_id, "NOT_A_REAL_WORK_STATUS")


def test_set_work_status_unknown_req_id_raises(store):
    with pytest.raises(KeyError):
        store.set_work_status("REQ-QA-SEC-999", "DONE")


def test_set_design_draft_gate_override_appends_shared_history(store):
    """§5-2 — override 필드도 design_draft_gate_history를 그대로 공유한다(신규 이력 없음)."""
    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0")

    updated = store.set_design_draft_gate_override(
        record.req_id, True, actor="pm@example.com", reason="별도 화면 필요",
    )
    assert updated.design_draft_gate_override is True
    assert len(updated.design_draft_gate_history) == 1
    assert updated.design_draft_gate_history[0]["field"] == "design_draft_gate_override"
