"""`PostgresTaskStore`/`PostgresTaskLockStore` 단위 테스트 — fake in-memory connection
(`tests/_fake_pg.py`)으로 SQL 생성·파라미터 바인딩·JSON 어댑터(`TaskStore`/`TaskLockStore`)와
동일 계약 준수 여부를 검증한다.

⚠ 실제 PostgreSQL 서버 없이 동작 — `backend/adapters/db/postgres/README.md`의 "검증 미확정"
상태를 해소하지 않는다(T98 AIP). 상태전이·서킷브레이커·배타락 로직이 JSON 어댑터와 동일한
domain 함수(`task_state_machine.py`/`conflict_detection.py`)를 그대로 재사용하는지 확인한다.
"""

import pytest

from backend.adapters.db.postgres.postgres_task_lock_store import PostgresTaskLockStore
from backend.adapters.db.postgres.postgres_task_store import PostgresTaskStore
from backend.adapters.persistence.task_lock_store import TaskLockConflictError
from backend.domain.entities.task import Task
from backend.domain.requirements.task_state_machine import InvalidTaskTransitionError
from tests._fake_pg import FakeConnection


def make_task(task_id="TASK-WAS-001", **overrides):
    fields = dict(
        task_id=task_id,
        domain_code="WAS",
        title="샘플 태스크",
        description="이 태스크는 충분한 길이의 설명을 가지고 있다" * 2,
        source_req_ids=["REQ-QA-SEC-001"],
        acceptance_criteria=["동작 확인"],
        impact_scope=["backend/x.py"],
        solution_stack=["FastAPI"],
    )
    fields.update(overrides)
    return Task(**fields)


@pytest.fixture
def conn():
    return FakeConnection()


@pytest.fixture
def store(conn):
    return PostgresTaskStore(conn=conn)


@pytest.fixture
def lock_store(conn):
    return PostgresTaskLockStore(conn=conn)


def test_create_or_update_persists_sufficient_task(store):
    task = make_task()
    saved = store.create_or_update(task)
    assert saved.needs_escalation is False
    assert saved.revision == 1

    fetched = store.get(task.task_id)
    assert fetched is not None
    assert fetched.title == "샘플 태스크"


def test_create_or_update_flags_insufficient_task_as_draft(store):
    task = make_task(description="짧음", acceptance_criteria=[], impact_scope=[], solution_stack=[], source_req_ids=[])
    task.status = "READY"
    saved = store.create_or_update(task)
    assert saved.needs_escalation is True
    assert saved.status == "DRAFT"


def test_create_or_update_increments_revision_on_second_call(store):
    task = make_task()
    store.create_or_update(task)
    again = make_task()
    saved = store.create_or_update(again)
    assert saved.revision == 2


def test_get_returns_none_for_unknown_task(store):
    assert store.get("TASK-WAS-999") is None


def test_list_all_returns_all_tasks(store):
    store.create_or_update(make_task("TASK-WAS-001"))
    store.create_or_update(make_task("TASK-WAS-002"))
    tasks = store.list_all()
    assert {t.task_id for t in tasks} == {"TASK-WAS-001", "TASK-WAS-002"}


def test_generate_task_id_increments_sequence(store):
    store.create_or_update(make_task("TASK-WAS-001"))
    next_id = store.generate_task_id("WAS")
    assert next_id == "TASK-WAS-002"


def test_generate_task_id_starts_at_one_when_empty(store):
    assert store.generate_task_id("WAS") == "TASK-WAS-001"


def test_set_status_valid_transition_appends_history(store):
    store.create_or_update(make_task(status="DRAFT"))
    # DRAFT -> READY 는 reason 불필요
    updated = store.set_status("TASK-WAS-001", "READY", actor="pm")
    assert updated.status == "READY"
    assert len(updated.status_history) == 1


def test_set_status_invalid_transition_raises(store):
    store.create_or_update(make_task(status="DRAFT"))
    with pytest.raises(InvalidTaskTransitionError):
        store.set_status("TASK-WAS-001", "DONE", actor="pm", reason="완료")


def test_set_status_unknown_task_raises(store):
    with pytest.raises(KeyError):
        store.set_status("TASK-WAS-999", "READY", actor="pm")


def test_set_status_entering_in_progress_acquires_lock(store, lock_store):
    store.create_or_update(make_task(status="DRAFT", impact_scope=["backend/x.py"]))
    store.set_status("TASK-WAS-001", "READY", actor="pm")
    store.set_status("TASK-WAS-001", "IN_PROGRESS", actor="pm")
    assert lock_store.held_by("TASK-WAS-001") == ["backend/x.py"]


def test_set_status_leaving_in_progress_releases_lock(store, lock_store):
    store.create_or_update(make_task(status="DRAFT", impact_scope=["backend/x.py"]))
    store.set_status("TASK-WAS-001", "READY", actor="pm")
    store.set_status("TASK-WAS-001", "IN_PROGRESS", actor="pm")
    store.set_status("TASK-WAS-001", "DONE", actor="pm", reason="완료 확인")
    assert lock_store.held_by("TASK-WAS-001") == []


def test_check_all_conflicts_delegates_to_domain_function(store):
    store.create_or_update(make_task("TASK-WAS-001"))
    result = store.check_all_conflicts()
    assert isinstance(result, dict)


# -- PostgresTaskLockStore -----------------------------------------------


def test_lock_acquire_and_release(lock_store):
    lock_store.acquire("TASK-WAS-001", ["a.py", "b.py"])
    assert lock_store.held_by("TASK-WAS-001") == ["a.py", "b.py"]
    lock_store.release("TASK-WAS-001")
    assert lock_store.held_by("TASK-WAS-001") == []


def test_lock_acquire_conflict_raises(lock_store):
    lock_store.acquire("TASK-WAS-001", ["a.py"])
    with pytest.raises(TaskLockConflictError):
        lock_store.acquire("TASK-WAS-002", ["a.py"])


def test_lock_acquire_same_task_reacquire_not_conflict(lock_store):
    lock_store.acquire("TASK-WAS-001", ["a.py"])
    lock_store.acquire("TASK-WAS-001", ["a.py", "b.py"])
    assert set(lock_store.held_by("TASK-WAS-001")) == {"a.py", "b.py"}


def test_lock_all_locks_returns_mapping(lock_store):
    lock_store.acquire("TASK-WAS-001", ["a.py"])
    lock_store.acquire("TASK-WAS-002", ["b.py"])
    assert lock_store.all_locks() == {"a.py": "TASK-WAS-001", "b.py": "TASK-WAS-002"}
