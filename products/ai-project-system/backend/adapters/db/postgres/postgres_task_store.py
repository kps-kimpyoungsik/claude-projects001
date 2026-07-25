"""`TaskStorePort`의 PostgreSQL 구현체 (2026-07-24 신설).

⚠ 검증 미확정 — README.md 참조. 비즈니스 로직(충분성 체크·상태전이 검증·서킷브레이커·
배타 락)은 `task_store.py`(JSON 어댑터)가 이미 import해 쓰는 동일한 domain 함수를
그대로 재사용한다 — 로직 재구현이 아니라 저장 메커니즘(JSON 파일 → PostgreSQL 테이블)만
교체(CRZ). `TaskStore`의 Port 외 공개 메서드(`generate_task_id`·`set_status`)도 동일하게
제공해 드롭인 교체가 가능하도록 했다.
"""

from dataclasses import asdict
from datetime import datetime, timezone

from backend.adapters.db.postgres.connection import get_connection
from backend.adapters.db.postgres.postgres_task_lock_store import PostgresTaskLockStore
from backend.application.ports.task_store_port import TaskStorePort
from backend.domain.entities.task import Task
from backend.domain.requirements.conflict_detection import check_sufficiency, detect_area_conflicts
from backend.domain.requirements.task_state_machine import (
    BLOCKED_CIRCUIT_BREAKER_THRESHOLD,
    build_status_change_event,
    check_circuit_breaker,
    count_blocked_transitions,
    validate_transition,
)

_LOCKED_STATUS = "IN_PROGRESS"


def _json(data: dict):
    from psycopg2.extras import Json
    return Json(data)


class PostgresTaskStore(TaskStorePort):
    def __init__(self, conn=None, lock_store: PostgresTaskLockStore | None = None):
        self._conn = conn
        self._lock_store = lock_store or PostgresTaskLockStore(conn)

    def _connection(self):
        return self._conn or get_connection()

    def create_or_update(self, task: Task, graph: dict | None = None) -> Task:
        sufficient, reasons = check_sufficiency(task, graph=graph)
        task.needs_escalation = not sufficient
        task.escalation_reasons = reasons
        if not sufficient and task.status not in ("DRAFT",):
            task.status = "DRAFT"
        task.updated_at = datetime.now(timezone.utc).isoformat()

        conn = self._connection()
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM tasks WHERE task_id = %s", (task.task_id,))
            existing = cur.fetchone()
            task.revision = (existing["data"]["revision"] + 1) if existing else 1
            data = asdict(task)
            cur.execute(
                "INSERT INTO tasks (task_id, status, data, updated_at) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (task_id) DO UPDATE SET status = EXCLUDED.status, "
                "data = EXCLUDED.data, updated_at = EXCLUDED.updated_at",
                (task.task_id, task.status, _json(data), task.updated_at),
            )
        conn.commit()
        return task

    def get(self, task_id: str) -> Task | None:
        conn = self._connection()
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM tasks WHERE task_id = %s", (task_id,))
            row = cur.fetchone()
        return Task(**row["data"]) if row else None

    def list_all(self) -> list[Task]:
        conn = self._connection()
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM tasks ORDER BY task_id")
            rows = cur.fetchall()
        return [Task(**r["data"]) for r in rows]

    def check_all_conflicts(self) -> dict:
        return detect_area_conflicts(self.list_all())

    def generate_task_id(self, domain_code: str) -> str:
        conn = self._connection()
        prefix = f"TASK-{domain_code}-"
        with conn.cursor() as cur:
            cur.execute("SELECT task_id FROM tasks WHERE task_id LIKE %s", (f"{prefix}%",))
            existing_seqs = [
                int(r["task_id"][len(prefix):])
                for r in cur.fetchall()
                if r["task_id"][len(prefix):].isdigit()
            ]
        next_seq = max(existing_seqs, default=0) + 1
        return f"{prefix}{next_seq:03d}"

    def set_status(
        self, task_id: str, status: str, actor: str,
        reason: str | None = None, override_escalation: bool = False,
    ) -> Task:
        conn = self._connection()
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM tasks WHERE task_id = %s", (task_id,))
            row = cur.fetchone()
            if not row:
                raise KeyError(f"존재하지 않는 task_id: {task_id}")
            record = row["data"]

            from_status = record["status"]
            check_circuit_breaker(record.get("needs_escalation", False), override_escalation, status)
            validate_transition(from_status, status, reason)

            entering_in_progress = status == _LOCKED_STATUS and from_status != _LOCKED_STATUS
            leaving_in_progress = from_status == _LOCKED_STATUS and status != _LOCKED_STATUS
            if entering_in_progress:
                self._lock_store.acquire(task_id, record.get("impact_scope", []))

            event = build_status_change_event(from_status, status, actor, reason)
            record.setdefault("status_history", []).append(event)
            record["status"] = status
            record["updated_at"] = datetime.now(timezone.utc).isoformat()

            if status == "BLOCKED" and count_blocked_transitions(record["status_history"]) >= BLOCKED_CIRCUIT_BREAKER_THRESHOLD:
                record["needs_escalation"] = True
                record.setdefault("escalation_reasons", []).append(
                    f"서킷 브레이커: BLOCKED {BLOCKED_CIRCUIT_BREAKER_THRESHOLD}회 이상 도달 — 사람 검토 필요"
                )
            elif override_escalation and record.get("needs_escalation") and status != "BLOCKED":
                record["needs_escalation"] = False
                record["escalation_reasons"] = []

            cur.execute(
                "UPDATE tasks SET status = %s, data = %s, updated_at = %s WHERE task_id = %s",
                (status, _json(record), record["updated_at"], task_id),
            )
        conn.commit()

        if leaving_in_progress:
            self._lock_store.release(task_id)
        return Task(**record)
