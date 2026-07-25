from backend.adapters.persistence.requirement_store import RequirementRecord
from backend.application.services.failure_pattern_analysis_service import (
    analyze_requirement_review_patterns,
    analyze_task_escalation_patterns,
)
from backend.domain.entities.task import Task


def _req(req_id, doc_type_code, area_code, lifecycle_status="UNDER_REVIEW", doc_conf=0.4, area_conf=0.4):
    return RequirementRecord(
        req_id=req_id,
        doc_type_code=doc_type_code,
        area_code=area_code,
        description="설명",
        source_ref="doc::x",
        doc_type_confidence=doc_conf,
        area_confidence=area_conf,
        lifecycle_status=lifecycle_status,
    )


def test_requirement_review_patterns_groups_and_sorts_by_count():
    reqs = [
        _req("REQ-BIZ-SEC-001", "BIZ", "SEC"),
        _req("REQ-BIZ-SEC-002", "BIZ", "SEC"),
        _req("REQ-QA-WEB-001", "QA", "WEB"),
        _req("REQ-BIZ-SEC-003", "BIZ", "SEC", lifecycle_status="ACCEPTED"),  # 이미 검토완료 -> 제외
    ]
    patterns = analyze_requirement_review_patterns(reqs)

    assert patterns[0]["doc_type_code"] == "BIZ"
    assert patterns[0]["area_code"] == "SEC"
    assert patterns[0]["count"] == 2
    assert patterns[0]["example_req_ids"] == ["REQ-BIZ-SEC-001", "REQ-BIZ-SEC-002"]
    assert patterns[1]["count"] == 1
    assert sum(p["count"] for p in patterns) == 3  # ACCEPTED 1건은 집계에서 빠짐


def test_requirement_review_patterns_empty_when_no_under_review():
    assert analyze_requirement_review_patterns([_req("R1", "BIZ", "SEC", lifecycle_status="ACCEPTED")]) == []


def _task(task_id, domain_code, needs_escalation=True, reasons=None):
    # reasons=None -> 기본값 사용, reasons=[] -> 명시적 "사유 없음"(placeholder 테스트용)
    # 이 둘을 `or`로 뭉뚱그리면 []도 falsy라 기본값으로 덮여써지는 실수가 생긴다.
    resolved_reasons = ["impact_scope 미지정"] if reasons is None else reasons
    return Task(
        task_id=task_id,
        domain_code=domain_code,
        title="t",
        description="충분히 긴 설명 텍스트로 최소 길이 요건을 충족시킨다",
        needs_escalation=needs_escalation,
        escalation_reasons=resolved_reasons,
    )


def test_task_escalation_patterns_groups_by_domain_and_reason():
    tasks = [
        _task("T-1", "WEB", reasons=["impact_scope 미지정"]),
        _task("T-2", "WEB", reasons=["impact_scope 미지정"]),
        _task("T-3", "SEC", reasons=["solution_stack 미지정"]),
        _task("T-4", "SEC", needs_escalation=False),  # 해소됨 -> 제외
    ]
    patterns = analyze_task_escalation_patterns(tasks)

    assert patterns[0]["domain_code"] == "WEB"
    assert patterns[0]["reason"] == "impact_scope 미지정"
    assert patterns[0]["count"] == 2
    assert patterns[0]["example_task_ids"] == ["T-1", "T-2"]
    assert sum(p["count"] for p in patterns) == 3


def test_task_escalation_patterns_uses_placeholder_for_missing_reason():
    tasks = [_task("T-1", "WEB", reasons=[])]
    patterns = analyze_task_escalation_patterns(tasks)
    assert patterns[0]["reason"] == "(사유 미기재)"
