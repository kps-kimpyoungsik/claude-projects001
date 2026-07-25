import pytest

from backend.adapters.persistence.task_store import TaskStore
from backend.domain.entities.task import Task


def _make_task(task_id="T-1") -> Task:
    return Task(
        task_id=task_id,
        domain_code="WEB",
        title="테스트 태스크",
        description="충분히 긴 설명 텍스트로 최소 길이 요건을 충족시킨다",
        source_req_ids=["REQ-TECH-WEB-001"],
        acceptance_criteria=["동작 확인"],
        impact_scope=["frontend/views/x.html"],
        solution_stack=["FastAPI"],
    )


def test_set_status_success_appends_history(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    store.create_or_update(_make_task())

    updated = store.set_status("T-1", "READY", actor="hong.gildong")
    assert updated.status == "READY"
    assert len(updated.status_history) == 1
    assert updated.status_history[0]["from_status"] == "DRAFT"
    assert updated.status_history[0]["to_status"] == "READY"

    updated = store.set_status("T-1", "IN_PROGRESS", actor="hong.gildong")
    assert updated.status == "IN_PROGRESS"
    assert len(updated.status_history) == 2


def test_set_status_persists_across_reload(tmp_path):
    path = tmp_path / "tasks.json"
    store = TaskStore(path)
    store.create_or_update(_make_task())
    store.set_status("T-1", "READY", actor="hong.gildong")

    reloaded = TaskStore(path)
    task = reloaded.get("T-1")
    assert task.status == "READY"
    assert len(task.status_history) == 1


def test_set_status_missing_task_raises_keyerror(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    with pytest.raises(KeyError):
        store.set_status("NOPE", "READY", actor="hong.gildong")


def test_set_status_invalid_transition_raises_valueerror(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    store.create_or_update(_make_task())
    with pytest.raises(ValueError):
        store.set_status("T-1", "DONE", actor="hong.gildong", reason="완료")  # DRAFT -> DONE 직행 금지(reason 있어도 거부)


def test_set_status_blocked_without_reason_raises(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    store.create_or_update(_make_task())
    store.set_status("T-1", "READY", actor="hong.gildong")
    with pytest.raises(ValueError, match="reason이 필수"):
        store.set_status("T-1", "BLOCKED", actor="hong.gildong")


def test_in_progress_transition_locks_impact_scope(tmp_path):
    """[Phase 4.3] IN_PROGRESS 진입 = impact_scope 배타 점유."""
    store = TaskStore(tmp_path / "tasks.json")
    store.create_or_update(_make_task())
    store.set_status("T-1", "READY", actor="hong.gildong")
    store.set_status("T-1", "IN_PROGRESS", actor="hong.gildong")

    assert store._lock_store.held_by("T-1") == ["frontend/views/x.html"]


def test_overlapping_impact_scope_second_task_rejected(tmp_path):
    """겹치는 impact_scope를 가진 두 Task가 동시에 IN_PROGRESS로 갈 수 없다(병렬 작업 통제)."""
    store = TaskStore(tmp_path / "tasks.json")
    store.create_or_update(_make_task("T-1"))
    store.create_or_update(_make_task("T-2"))  # 동일 impact_scope: frontend/views/x.html

    store.set_status("T-1", "READY", actor="hong.gildong")
    store.set_status("T-1", "IN_PROGRESS", actor="hong.gildong")

    store.set_status("T-2", "READY", actor="hong.gildong")
    with pytest.raises(ValueError, match="impact_scope 충돌"):
        store.set_status("T-2", "IN_PROGRESS", actor="hong.gildong")

    # 거부됐으므로 T-2는 여전히 READY(부분 반영 없음)
    assert store.get("T-2").status == "READY"


def test_circuit_breaker_trip_and_override_reset_via_store(tmp_path):
    """[Phase 5.3] TaskStore 레벨에서 서킷 브레이커 트립 + override 리셋(escalation_reasons
    포함) 확인 — API 레벨 E2E(test_e2e_task_lifecycle.py)와 상보적으로 store 내부 상태까지 검증."""
    from backend.domain.requirements.task_state_machine import HumanReviewRequiredError

    store = TaskStore(tmp_path / "tasks.json")
    store.create_or_update(_make_task())
    store.set_status("T-1", "READY", actor="x")

    for _ in range(2):
        store.set_status("T-1", "BLOCKED", actor="x", reason="의존성 미해결")
        store.set_status("T-1", "READY", actor="x")

    tripped = store.set_status("T-1", "BLOCKED", actor="x", reason="의존성 미해결")
    assert tripped.needs_escalation is True
    assert tripped.escalation_reasons

    with pytest.raises(HumanReviewRequiredError):
        store.set_status("T-1", "READY", actor="x")

    reset = store.set_status("T-1", "READY", actor="human-reviewer", override_escalation=True)
    assert reset.needs_escalation is False
    assert reset.escalation_reasons == []


def test_leaving_in_progress_releases_lock_and_unblocks_other_task(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    store.create_or_update(_make_task("T-1"))
    store.create_or_update(_make_task("T-2"))

    store.set_status("T-1", "READY", actor="hong.gildong")
    store.set_status("T-1", "IN_PROGRESS", actor="hong.gildong")
    store.set_status("T-1", "DONE", actor="hong.gildong", reason="완료 확인")  # 이탈 -> 락 해제

    store.set_status("T-2", "READY", actor="hong.gildong")
    updated = store.set_status("T-2", "IN_PROGRESS", actor="hong.gildong")  # 이제는 허용
    assert updated.status == "IN_PROGRESS"
