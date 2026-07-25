"""task_dispatch_service — compute_priority 정렬 + dispatch_tasks CLEAR/OVERLAP 분기 회귀 테스트."""

from backend.adapters.persistence.requirement_store import RequirementRecord, RequirementStore
from backend.adapters.persistence.task_store import TaskStore
from backend.application.services.agent_dispatch_resolver import AgentResolution
from backend.application.services.task_dispatch_service import (
    compute_priority,
    dispatch_tasks,
    sync_requirement_work_status,
)
from backend.domain.entities.task import Task


def _req(req_id, lifecycle_status):
    return RequirementRecord(
        req_id=req_id,
        doc_type_code="BIZ",
        area_code="SEC",
        description="x",
        source_ref="doc::0",
        doc_type_confidence=0.9,
        area_confidence=0.9,
        lifecycle_status=lifecycle_status,
    )


def _task(**overrides):
    defaults = dict(
        task_id="T1",
        domain_code="SEC",
        title="x",
        description="결제 암호화 태스크 상세 설명 20자 이상",
        acceptance_criteria=["AES256 적용"],
        impact_scope=["backend/adapters/db/sqlite_adapter.py"],
        source_req_ids=["REQ-BIZ-SEC-001"],
        solution_stack=["전자정부표준프레임워크"],
    )
    defaults.update(overrides)
    return Task(**defaults)


def test_compute_priority_prefers_accepted_requirement():
    accepted_req = _req("REQ-BIZ-SEC-001", "ACCEPTED")
    review_req = _req("REQ-BIZ-SEC-002", "UNDER_REVIEW")

    task_accepted = _task(task_id="A", source_req_ids=["REQ-BIZ-SEC-001"])
    task_review = _task(task_id="B", source_req_ids=["REQ-BIZ-SEC-002"])

    all_reqs = [accepted_req, review_req]
    assert compute_priority(task_accepted, all_reqs) < compute_priority(task_review, all_reqs)


def test_compute_priority_deprioritizes_needs_escalation():
    accepted_req = _req("REQ-BIZ-SEC-001", "ACCEPTED")
    task_ok = _task(task_id="A", needs_escalation=False)
    task_escalated = _task(task_id="B", needs_escalation=True)

    all_reqs = [accepted_req]
    assert compute_priority(task_ok, all_reqs) < compute_priority(task_escalated, all_reqs)


def test_dispatch_tasks_marks_overlap_sequential_and_clear_parallel(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    store.create_or_update(_task(task_id="A", impact_scope=["shared/x.py"]))
    store.create_or_update(_task(task_id="B", impact_scope=["shared/x.py"]))
    store.create_or_update(_task(task_id="C", impact_scope=["independent/y.py"]))

    def fake_resolve_fn(domain_code):
        return AgentResolution(
            domain_code=domain_code,
            agent_command="/aegis-security",
            source="fallback_default",
            score=None,
            resolved_at="2026-07-19T00:00:00+00:00",
        )

    plan = dispatch_tasks(store, all_requirements=[], resolve_fn=fake_resolve_fn)
    plan_by_id = {p["task_id"]: p for p in plan}

    assert plan_by_id["A"]["dispatch_mode"] == "sequential"
    assert plan_by_id["B"]["dispatch_mode"] == "sequential"
    assert plan_by_id["C"]["dispatch_mode"] == "parallel"
    assert all(p["agent_resolution"].agent_command == "/aegis-security" for p in plan)


def _seed_requirement_store(tmp_path, req_ids):
    from dataclasses import asdict

    store = RequirementStore(tmp_path / "requirements_store.json")
    data = {}
    for req_id in req_ids:
        record = _req(req_id, "ACCEPTED")
        data[req_id] = asdict(record)
    store._save_all(data)
    return store


def _resolution(agent_command):
    return AgentResolution(
        domain_code="SEC", agent_command=agent_command, source="fallback_default",
        score=None, resolved_at="2026-07-20T00:00:00+00:00",
    )


def test_sync_requirement_work_status_reflects_in_progress(tmp_path):
    """06_AGENT_DISPATCH_REPORTING.md §10-2/§10-3 — 참조 Task가 IN_PROGRESS면 REQ도 그렇게."""
    task_store = TaskStore(tmp_path / "tasks.json")
    task_store.create_or_update(_task(task_id="A", status="IN_PROGRESS", source_req_ids=["REQ-BIZ-SEC-001"]))
    req_store = _seed_requirement_store(tmp_path, ["REQ-BIZ-SEC-001"])

    plan = dispatch_tasks(task_store, all_requirements=req_store.list_all(), resolve_fn=lambda d: _resolution("/aegis-security"))
    sync_requirement_work_status(req_store, task_store, plan)

    updated = {r.req_id: r for r in req_store.list_all()}["REQ-BIZ-SEC-001"]
    assert updated.work_status == "IN_PROGRESS"
    assert updated.assigned_agent_command == "/aegis-security"


def test_sync_requirement_work_status_prioritizes_blocked_over_in_progress(tmp_path):
    """§10-2 표 — 여러 Task가 같은 REQ를 참조할 때 BLOCKED가 우선(문제 은폐 방지)."""
    task_store = TaskStore(tmp_path / "tasks.json")
    task_store.create_or_update(_task(task_id="A", status="IN_PROGRESS", source_req_ids=["REQ-BIZ-SEC-001"]))
    task_store.create_or_update(_task(task_id="B", status="BLOCKED", source_req_ids=["REQ-BIZ-SEC-001"], impact_scope=["other/x.py"]))
    req_store = _seed_requirement_store(tmp_path, ["REQ-BIZ-SEC-001"])

    plan = dispatch_tasks(task_store, all_requirements=req_store.list_all(), resolve_fn=lambda d: _resolution("/aegis-security"))
    sync_requirement_work_status(req_store, task_store, plan)

    updated = {r.req_id: r for r in req_store.list_all()}["REQ-BIZ-SEC-001"]
    assert updated.work_status == "BLOCKED"


def test_sync_requirement_work_status_done_only_when_all_tasks_done(tmp_path):
    """§10-2 — 부분 완료는 낙관적으로 앞당기지 않는다(전부 DONE일 때만 DONE)."""
    task_store = TaskStore(tmp_path / "tasks.json")
    task_store.create_or_update(_task(task_id="A", status="DONE", source_req_ids=["REQ-BIZ-SEC-001"]))
    task_store.create_or_update(_task(task_id="B", status="READY", source_req_ids=["REQ-BIZ-SEC-001"], impact_scope=["other/x.py"]))
    req_store = _seed_requirement_store(tmp_path, ["REQ-BIZ-SEC-001"])

    plan = dispatch_tasks(task_store, all_requirements=req_store.list_all(), resolve_fn=lambda d: _resolution("/aegis-security"))
    sync_requirement_work_status(req_store, task_store, plan)

    updated = {r.req_id: r for r in req_store.list_all()}["REQ-BIZ-SEC-001"]
    assert updated.work_status == "DISPATCHED"

    # 나머지 하나도 DONE이 되면 전체 DONE
    task_store.create_or_update(_task(task_id="B", status="DONE", source_req_ids=["REQ-BIZ-SEC-001"], impact_scope=["other/x.py"]))
    plan2 = dispatch_tasks(task_store, all_requirements=req_store.list_all(), resolve_fn=lambda d: _resolution("/aegis-security"))
    sync_requirement_work_status(req_store, task_store, plan2)
    updated2 = {r.req_id: r for r in req_store.list_all()}["REQ-BIZ-SEC-001"]
    assert updated2.work_status == "DONE"


def test_sync_requirement_work_status_not_dispatched_when_no_task_references(tmp_path):
    task_store = TaskStore(tmp_path / "tasks.json")
    req_store = _seed_requirement_store(tmp_path, ["REQ-BIZ-SEC-001"])

    plan = dispatch_tasks(task_store, all_requirements=req_store.list_all(), resolve_fn=lambda d: _resolution("/aegis-security"))
    sync_requirement_work_status(req_store, task_store, plan)

    updated = {r.req_id: r for r in req_store.list_all()}["REQ-BIZ-SEC-001"]
    assert updated.work_status == "NOT_DISPATCHED"
    assert updated.assigned_agent_command is None
