"""backend.domain.task — 태스크 충분성 게이트·N x N 충돌탐지 회귀 테스트."""

from backend.domain.entities.task import Task
from backend.domain.requirements.conflict_detection import (
    check_sufficiency,
    detect_area_conflicts,
    detect_conflicts_within_groups,
    group_tasks_by_area_layer,
)


def _valid_task(**overrides):
    defaults = dict(
        task_id="T1",
        domain_code="SEC",
        title="x",
        description="결제 암호화 태스크 상세 설명 20자 이상",
        acceptance_criteria=["AES256 적용"],
        impact_scope=["backend/adapters/db/sqlite_adapter.py"],
        source_req_ids=["REQ-BIZ-SEC-003"],
        solution_stack=["전자정부표준프레임워크"],
    )
    defaults.update(overrides)
    return Task(**defaults)


def test_sufficient_task_passes():
    ok, reasons = check_sufficiency(_valid_task())
    assert ok is True
    assert reasons == []


def test_missing_solution_stack_fails():
    ok, reasons = check_sufficiency(_valid_task(solution_stack=[]))
    assert ok is False
    assert any("solution_stack" in r for r in reasons)


def test_missing_source_req_ids_fails():
    ok, reasons = check_sufficiency(_valid_task(source_req_ids=[]))
    assert ok is False
    assert any("source_req_ids" in r or "요구사항" in r for r in reasons)


def test_detect_area_conflicts_finds_overlapping_files():
    a = _valid_task(task_id="A", impact_scope=["shared/x.py"])
    b = _valid_task(task_id="B", impact_scope=["shared/x.py"])
    c = _valid_task(task_id="C", impact_scope=["independent/y.py"])
    result = detect_area_conflicts([a, b, c])
    assert result["overlap_pairs"] == 1
    assert result["pairs"][0]["overlap"] == ["shared/x.py"]


def test_group_tasks_by_area_layer_groups_by_domain_and_layer():
    # plans/_plan/02_PHASE2_ORCHESTRATION_PREVIEW.md §3-1
    a = _valid_task(task_id="A", domain_code="WEB", source_req_ids=["REQ-BIZ-WEB-001"],
                     impact_scope=["frontend/x.tsx"])
    b = _valid_task(task_id="B", domain_code="SEC", source_req_ids=["REQ-BIZ-SEC-003"],
                     impact_scope=["backend/adapters/db/sqlite_adapter.py"])
    c = _valid_task(task_id="C", domain_code="DB", source_req_ids=["REQ-BIZ-DB-002"],
                     impact_scope=["backend/adapters/db/sqlite_adapter.py"])
    layer_by_req_id = {
        "REQ-BIZ-WEB-001": "UXENV",
        "REQ-BIZ-SEC-003": "SYS",
        "REQ-BIZ-DB-002": "SYS",
    }
    groups = group_tasks_by_area_layer([a, b, c], layer_by_req_id)

    assert groups[("WEB", "UXENV")] == [a]
    assert groups[("SEC", "SYS")] == [b]
    assert groups[("DB", "SYS")] == [c]
    assert len(groups) == 3


def test_group_tasks_by_area_layer_unspecified_when_no_layer_lookup():
    a = _valid_task(task_id="A", domain_code="WEB", source_req_ids=["REQ-BIZ-WEB-001"])
    groups = group_tasks_by_area_layer([a])  # layer_by_req_id 미전달
    assert groups[("WEB", "UNSPECIFIED")] == [a]


def test_detect_conflicts_within_groups_catches_overlap_inside_same_group():
    # 설계서 §3-2 "이중 안전망" — 같은 (domain, layer) 그룹이라도 impact_scope가 겹치면
    # 여전히 conflict로 잡혀 순차화 대상이 되어야 한다.
    b = _valid_task(task_id="B", domain_code="SEC", source_req_ids=["REQ-BIZ-SEC-003"],
                     impact_scope=["backend/adapters/db/sqlite_adapter.py"])
    c = _valid_task(task_id="C", domain_code="SEC", source_req_ids=["REQ-BIZ-SEC-004"],
                     impact_scope=["backend/adapters/db/sqlite_adapter.py"])
    layer_by_req_id = {"REQ-BIZ-SEC-003": "SYS", "REQ-BIZ-SEC-004": "SYS"}
    groups = group_tasks_by_area_layer([b, c], layer_by_req_id)

    assert list(groups.keys()) == [("SEC", "SYS")]  # 같은 그룹으로 묶임

    conflicts = detect_conflicts_within_groups(groups)
    result = conflicts[("SEC", "SYS")]
    assert result["overlap_pairs"] == 1
    assert result["pairs"][0]["overlap"] == ["backend/adapters/db/sqlite_adapter.py"]
