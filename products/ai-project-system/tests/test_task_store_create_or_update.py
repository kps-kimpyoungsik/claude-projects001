"""TaskStore.create_or_update()/check_all_conflicts() 단위 테스트 — 지금까지 status
전이(set_status)만 전용 테스트가 있었고 create_or_update()의 재승격 방지 분기와
check_all_conflicts()는 전용 테스트가 없었다."""

from backend.adapters.persistence.task_store import TaskStore
from backend.domain.entities.task import Task


def _sufficient_task(**overrides):
    defaults = dict(
        task_id="TASK-SEC-001",
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


def test_create_or_update_demotes_previously_promoted_task_when_becoming_insufficient(tmp_path):
    """[커버리지 보완] 이미 READY 등으로 승격된 태스크가 재저장 시 내용 부족으로 판정되면
    (예: acceptance_criteria가 비워짐) DRAFT로 강제 강등된다 — 불충분한 태스크가 실행
    가능 상태로 남아있지 않도록 하는 안전장치."""
    store = TaskStore(tmp_path / "tasks.json")
    task = _sufficient_task(status="READY")
    saved = store.create_or_update(task)
    assert saved.status == "READY"

    now_insufficient = _sufficient_task(status="READY", acceptance_criteria=[])
    demoted = store.create_or_update(now_insufficient)
    assert demoted.status == "DRAFT"
    assert demoted.needs_escalation is True


def test_check_all_conflicts_detects_impact_scope_overlap(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    store.create_or_update(_sufficient_task(task_id="TASK-SEC-001", impact_scope=["shared/x.py"]))
    store.create_or_update(_sufficient_task(task_id="TASK-SEC-002", impact_scope=["shared/x.py"]))

    result = store.check_all_conflicts()
    assert result["overlap_pairs"] == 1
