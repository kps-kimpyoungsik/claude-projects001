"""`backend/application/services/context_service.py` 단위 테스트.

이 모듈은 (a) 카테고리 — 완결된 실 구현체다(단일 JSON 파일 기반 영속 상태, 외부 의존 없음).
`TaskStateStore`(load/save)와 `prune_context`(Context Pruning)를 검증한다.
"""

from backend.application.services.context_service import TaskState, TaskStateStore, prune_context


def test_load_returns_none_when_file_missing(tmp_path):
    store = TaskStateStore(tmp_path / "state.json")
    assert store.load("TASK-WAS-001") is None


def test_save_then_load_roundtrip(tmp_path):
    store = TaskStateStore(tmp_path / "state.json")
    state = TaskState(task_id="TASK-WAS-001", status="IMPLEMENTING", decisions=["결정1"])
    store.save(state)

    loaded = store.load("TASK-WAS-001")
    assert loaded is not None
    assert loaded.task_id == "TASK-WAS-001"
    assert loaded.status == "IMPLEMENTING"
    assert loaded.decisions == ["결정1"]


def test_load_returns_none_for_unknown_task_id_in_existing_file(tmp_path):
    store = TaskStateStore(tmp_path / "state.json")
    store.save(TaskState(task_id="TASK-WAS-001", status="WAITING"))
    assert store.load("TASK-WAS-999") is None


def test_save_preserves_other_task_records(tmp_path):
    store = TaskStateStore(tmp_path / "state.json")
    store.save(TaskState(task_id="TASK-WAS-001", status="WAITING"))
    store.save(TaskState(task_id="TASK-WAS-002", status="TESTING"))

    assert store.load("TASK-WAS-001").status == "WAITING"
    assert store.load("TASK-WAS-002").status == "TESTING"


def test_save_overwrites_existing_record_for_same_task_id(tmp_path):
    store = TaskStateStore(tmp_path / "state.json")
    store.save(TaskState(task_id="TASK-WAS-001", status="WAITING"))
    store.save(TaskState(task_id="TASK-WAS-001", status="VERIFIED"))
    assert store.load("TASK-WAS-001").status == "VERIFIED"


def test_task_state_defaults_to_empty_decisions():
    state = TaskState(task_id="TASK-WAS-001", status="WAITING")
    assert state.decisions == []


def test_prune_context_keeps_last_n_when_over_limit():
    decisions = [f"결정{i}" for i in range(15)]
    pruned = prune_context(decisions, keep_last=10)
    assert pruned == decisions[-10:]
    assert len(pruned) == 10


def test_prune_context_returns_all_when_under_limit():
    decisions = ["a", "b", "c"]
    assert prune_context(decisions, keep_last=10) == decisions


def test_prune_context_returns_all_when_exactly_at_limit():
    decisions = [f"d{i}" for i in range(10)]
    assert prune_context(decisions, keep_last=10) == decisions
