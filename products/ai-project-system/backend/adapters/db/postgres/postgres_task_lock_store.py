"""`task_lock_store.TaskLockStore`(파일 기반)와 동일 공개 API를 제공하는 PostgreSQL 구현체
(2026-07-24 신설).

⚠ 검증 미확정 — README.md 참조. `TaskLockStore`는 Port(ABC)가 없는 구체 클래스라 여기서도
동일한 4개 메서드(acquire/release/held_by/all_locks)만 제공한다(신규 계약 발명 없음, CRZ).
"""

from backend.adapters.db.postgres.connection import get_connection
from backend.adapters.persistence.task_lock_store import TaskLockConflictError


class PostgresTaskLockStore:
    def __init__(self, conn=None):
        self._conn = conn

    def _connection(self):
        return self._conn or get_connection()

    def acquire(self, task_id: str, impact_scope: list[str]) -> None:
        """impact_scope 전체를 점유 시도 — 하나라도 다른 task_id가 이미 점유 중이면 전부
        거부한다(JSON 어댑터와 동일: 부분 점유 금지, 같은 task_id 재점유는 충돌 아님).

        단일 트랜잭션으로 검사+삽입을 묶어 파일 기반 버전보다 오히려 동시성에 더 안전하다
        (동시 acquire 경쟁 시 DB 트랜잭션 격리가 파일 read-modify-write보다 원자적) — 다만
        이 이점 자체도 실제 동시 요청으로 검증되지는 않았다(미확정).
        """
        conn = self._connection()
        with conn.cursor() as cur:
            if impact_scope:
                cur.execute(
                    "SELECT path, task_id FROM task_locks WHERE path = ANY(%s) AND task_id != %s",
                    (impact_scope, task_id),
                )
                conflicts = {r["path"]: r["task_id"] for r in cur.fetchall()}
                if conflicts:
                    raise TaskLockConflictError(
                        f"impact_scope 충돌 — 다른 Task가 이미 점유 중(병렬 진행 불가): {conflicts}"
                    )
            for path in impact_scope:
                cur.execute(
                    "INSERT INTO task_locks (path, task_id) VALUES (%s, %s) "
                    "ON CONFLICT (path) DO UPDATE SET task_id = EXCLUDED.task_id",
                    (path, task_id),
                )
        conn.commit()

    def release(self, task_id: str) -> None:
        conn = self._connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM task_locks WHERE task_id = %s", (task_id,))
        conn.commit()

    def held_by(self, task_id: str) -> list[str]:
        conn = self._connection()
        with conn.cursor() as cur:
            cur.execute("SELECT path FROM task_locks WHERE task_id = %s ORDER BY path", (task_id,))
            return [r["path"] for r in cur.fetchall()]

    def all_locks(self) -> dict[str, str]:
        conn = self._connection()
        with conn.cursor() as cur:
            cur.execute("SELECT path, task_id FROM task_locks")
            return {r["path"]: r["task_id"] for r in cur.fetchall()}
