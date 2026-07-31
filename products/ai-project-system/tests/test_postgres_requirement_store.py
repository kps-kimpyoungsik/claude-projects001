"""`PostgresRequirementStore` 단위 테스트 — fake in-memory connection(`tests/_fake_pg.py`)으로
SQL 생성·파라미터 바인딩·JSON 어댑터(`RequirementStore`)와 동일 계약 준수 여부를 검증한다.

⚠ 실제 PostgreSQL 서버 없이 동작 — `backend/adapters/db/postgres/README.md`의 "검증 미확정"
상태를 해소하지 않는다(T98 AIP). 여기서 확인하는 것은 채번·상태전이·감사이력 로직이
JSON 어댑터(`requirement_store.py`)와 동일하게 재사용되는지, SQL 파라미터 바인딩이
기대대로 이뤄지는지다.
"""

import pytest

from backend.adapters.db.postgres.postgres_requirement_store import PostgresRequirementStore
from backend.domain.requirements.classifier import classify_chunk
from tests._fake_pg import FakeConnection

SECURITY_TEXT = "# 보안 요건\n암호화 솔루션과 SSL 인증서를 적용하고 소스코드 취약성 점검을 수행한다."


@pytest.fixture
def store():
    return PostgresRequirementStore(conn=FakeConnection())


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


def test_sequential_seq_numbers_within_same_doc_area(store):
    classification = classify_chunk(SECURITY_TEXT)
    r1 = store.add_from_classification(classification, description="a", source_ref="doc::child:0")
    r2 = store.add_from_classification(classification, description="b", source_ref="doc::child:1")
    assert r1.req_id != r2.req_id
    assert r2.req_id.endswith("002") or r1.req_id.endswith("002")


def test_set_status_requires_reason_for_rejected(store):
    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0")

    with pytest.raises(ValueError):
        store.set_status(record.req_id, "REJECTED", actor="pm@example.com")

    updated = store.set_status(record.req_id, "REJECTED", actor="pm@example.com", reason="요구사항 변경")
    assert updated.lifecycle_status == "REJECTED"
    assert len(updated.status_history) == 1
    assert updated.status_history[0]["actor"] == "pm@example.com"


def test_set_status_rejects_unknown_status(store):
    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0")
    with pytest.raises(ValueError):
        store.set_status(record.req_id, "NOT_A_REAL_STATUS", actor="pm")


def test_set_design_draft_gate_updates_confidence_to_1(store):
    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0")
    from backend.domain.requirements.codes import DESIGN_GATE_VALUES

    value = next(iter(DESIGN_GATE_VALUES))
    updated = store.set_design_draft_gate(record.req_id, value, actor="pm")
    assert updated.design_draft_gate == value
    assert updated.design_draft_gate_confidence == 1.0


def test_set_design_draft_gate_rejects_unknown_value(store):
    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0")
    with pytest.raises(ValueError):
        store.set_design_draft_gate(record.req_id, "NOT_A_REAL_GATE", actor="pm")


def test_set_design_draft_gate_override_records_history(store):
    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0")
    updated = store.set_design_draft_gate_override(record.req_id, True, actor="pm", reason="예외 승인")
    assert updated.design_draft_gate_override is True


def test_request_rechunk_marks_rejected_and_enqueues(store):
    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0")
    updated = store.request_rechunk(record.req_id, actor="pm", reason="경계 재설정 필요")
    assert updated.lifecycle_status == "REJECTED"
    assert len(store._connection().db["rechunk_queue"]) == 1


def test_set_work_status_updates_fields(store):
    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0")
    updated = store.set_work_status(record.req_id, "IN_PROGRESS", assigned_agent_command="/aegis-dev")
    assert updated.work_status == "IN_PROGRESS"
    assert updated.assigned_agent_command == "/aegis-dev"


def test_set_work_status_rejects_unknown_status(store):
    classification = classify_chunk(SECURITY_TEXT)
    record = store.add_from_classification(classification, description="보안 요건", source_ref="doc::child:0")
    with pytest.raises(ValueError):
        store.set_work_status(record.req_id, "NOT_A_REAL_WORK_STATUS")


def test_list_all_returns_all_records(store):
    classification = classify_chunk(SECURITY_TEXT)
    store.add_from_classification(classification, description="a", source_ref="doc::child:0")
    store.add_from_classification(classification, description="b", source_ref="doc::child:1")
    assert len(store.list_all()) == 2


