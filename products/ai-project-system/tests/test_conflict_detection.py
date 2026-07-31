"""conflict_detection.py 단위 테스트 — 지금까지 전용 테스트 파일이 없었다(간접적으로만
task_store.py 테스트를 통해 exercise됨)."""

from backend.domain.entities.task import Task
from backend.domain.graph.entities import NodeKind
from backend.domain.requirements.conflict_detection import (
    check_sufficiency,
    _resolve_layer_code,
    group_tasks_by_area_layer,
)


def _task(**overrides):
    defaults = dict(
        task_id="T1",
        domain_code="SEC",
        title="x",
        description="충분히 긴 설명 텍스트로 최소 길이 요건을 충족시킨다",
        acceptance_criteria=["동작 확인"],
        impact_scope=["a.py"],
        source_req_ids=["REQ-BIZ-SEC-001"],
        solution_stack=["FastAPI"],
    )
    defaults.update(overrides)
    return Task(**defaults)


def _graph_with(node_ids):
    return {"nodes": [{"node_id": nid, "kind": NodeKind.REQUIREMENT.value} for nid in node_ids]}


def test_check_sufficiency_with_graph_grounded_passes():
    """[커버리지 보완] graph가 주어지고 source_req_ids가 실제로 그래프에 존재하면 추가
    검증도 통과한다."""
    task = _task()
    graph = _graph_with(["REQ-BIZ-SEC-001"])
    sufficient, reasons = check_sufficiency(task, graph=graph)
    assert sufficient is True
    assert reasons == []


def test_check_sufficiency_with_graph_ungrounded_fails():
    """[커버리지 보완] graph가 주어졌는데 source_req_ids가 그래프에 없으면 "그래프에 없는
    요구사항 참조" 사유로 불충분 판정된다."""
    task = _task()
    graph = _graph_with(["REQ-OTHER-SEC-999"])  # task의 REQ-BIZ-SEC-001은 여기 없음
    sufficient, reasons = check_sufficiency(task, graph=graph)
    assert sufficient is False
    assert any("그래프에 없는 요구사항 참조" in r for r in reasons)


def test_check_sufficiency_missing_source_req_ids_reports_reason():
    """[커버리지 보완] source_req_ids가 비어있으면 graph 인자와 무관하게(elif 분기 자체를
    타지 않고) '요구사항 추적 근거 없음' 사유가 즉시 추가된다."""
    task = _task(source_req_ids=[])
    sufficient, reasons = check_sufficiency(task)
    assert sufficient is False
    assert any("요구사항 추적 근거" in r for r in reasons)


def test_resolve_layer_code_falls_back_to_unspecified_when_no_layer_found():
    """[커버리지 보완] source_req_ids가 가리키는 요구사항 중 layer_code가 있는 것이 하나도
    없으면 UNSPECIFIED로 정직하게 귀결된다."""
    task = _task(source_req_ids=["REQ-BIZ-SEC-001", "REQ-BIZ-SEC-002"])
    assert _resolve_layer_code(task, layer_by_req_id={}) == "UNSPECIFIED"


def test_group_tasks_by_area_layer_uses_unspecified_when_layer_map_missing():
    task = _task()
    groups = group_tasks_by_area_layer([task], layer_by_req_id=None)
    assert ("SEC", "UNSPECIFIED") in groups
