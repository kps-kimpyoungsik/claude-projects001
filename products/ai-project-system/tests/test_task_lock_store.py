import pytest

from backend.adapters.persistence.task_lock_store import TaskLockConflictError, TaskLockStore


def test_acquire_then_release(tmp_path):
    store = TaskLockStore(tmp_path / "locks.json")
    store.acquire("T-1", ["a.py", "b.py"])
    assert store.held_by("T-1") == ["a.py", "b.py"]

    store.release("T-1")
    assert store.held_by("T-1") == []
    assert store.all_locks() == {}


def test_acquire_conflict_rejects_and_does_not_partially_lock(tmp_path):
    store = TaskLockStore(tmp_path / "locks.json")
    store.acquire("T-1", ["a.py", "b.py"])

    with pytest.raises(TaskLockConflictError):
        store.acquire("T-2", ["b.py", "c.py"])

    # 부분 점유 없음 — c.py는 T-2가 시도했지만 충돌로 전부 거부되어 잠기지 않았어야 함
    assert store.held_by("T-2") == []
    assert store.held_by("T-1") == ["a.py", "b.py"]


def test_reacquire_same_task_is_idempotent(tmp_path):
    store = TaskLockStore(tmp_path / "locks.json")
    store.acquire("T-1", ["a.py"])
    store.acquire("T-1", ["a.py", "b.py"])  # 자기 자신의 재점유는 충돌 아님
    assert store.held_by("T-1") == ["a.py", "b.py"]


def test_release_persists_across_reload(tmp_path):
    path = tmp_path / "locks.json"
    store = TaskLockStore(path)
    store.acquire("T-1", ["a.py"])
    store.release("T-1")

    reloaded = TaskLockStore(path)
    assert reloaded.all_locks() == {}
