"""PostgreSQL 어댑터(`backend/adapters/db/postgres/*`) 단위 테스트용 인메모리 fake
connection/cursor.

목적: 실제 PostgreSQL 서버 없이 `postgres_*_store.py`의 SQL 생성 로직·파라미터 바인딩·
인터페이스 계약(JSON 어댑터와 동일 동작)을 검증한다. **실제 PostgreSQL 문법·타입 호환성을
검증하는 것이 아니다** — 이 fake는 이 저장소들이 실행하는 고정된 SQL 문자열 집합만
알고 있는 최소 해석기이며, 진짜 SQL 파서가 아니다(README.md "검증 미확정" 상태는 이
테스트로 해소되지 않음 — T98 AIP 정직성 원칙 그대로 유지).

각 postgres_*_store.py가 실제로 실행하는 SQL은 고정 문자열(파라미터는 %s 플레이스홀더)
이므로, 문자열 매칭만으로 충분하다 — 범용 SQL 엔진을 새로 만들지 않는다(CRZ).
"""

from copy import deepcopy


def _unwrap(value):
    """`psycopg2.extras.Json(...)`으로 감싼 파라미터를 원래 dict로 되돌린다."""
    return value.adapted if hasattr(value, "adapted") else value


class FakeCursor:
    def __init__(self, db: dict):
        self.db = db
        self._result: list[dict] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    # -- 조회 결과 --------------------------------------------------
    def fetchall(self):
        return deepcopy(self._result)

    def fetchone(self):
        return deepcopy(self._result[0]) if self._result else None

    # -- 실행 ------------------------------------------------------
    def execute(self, sql: str, params: tuple = ()):
        sql = " ".join(sql.split())
        self._result = []
        handler = _HANDLERS.get(sql)
        if handler is None:
            # ON CONFLICT류는 접두 매칭(문자열 그대로도 있지만 방어적으로 둠)
            for key, h in _HANDLERS.items():
                if sql.startswith(key.split(" ON CONFLICT")[0]) and "ON CONFLICT" in sql and "ON CONFLICT" in key:
                    handler = h
                    break
        if handler is None:
            raise AssertionError(f"FakeCursor가 모르는 SQL: {sql!r}")
        handler(self, params)


def _h_projects_select_all(cur, params):
    rows = sorted(cur.db["projects"].values(), key=lambda r: r["project_id"])
    cur._result = deepcopy(rows)


def _h_projects_select_ids(cur, params):
    cur._result = [{"project_id": pid} for pid in cur.db["projects"]]


def _h_projects_insert(cur, params):
    pid, status, data = params
    cur.db["projects"][pid] = {"project_id": pid, "status": status, "data": deepcopy(_unwrap(data))}


def _h_projects_select_one(cur, params):
    row = cur.db["projects"].get(params[0])
    cur._result = [deepcopy(row)] if row else []


def _h_projects_update_status(cur, params):
    status, pid = params
    if pid in cur.db["projects"]:
        cur.db["projects"][pid]["status"] = status


def _h_projects_upsert(cur, params):
    pid, status, data = params
    cur.db["projects"][pid] = {"project_id": pid, "status": status, "data": deepcopy(_unwrap(data))}


def _h_requirements_select_like(cur, params):
    prefix = params[0].rstrip("%")
    cur._result = [
        {"req_id": rid} for rid in cur.db["requirements"] if rid.startswith(prefix)
    ]


def _h_requirements_insert(cur, params):
    req_id, doc_type_code, area_code, lifecycle_status, data = params
    cur.db["requirements"][req_id] = deepcopy(_unwrap(data))


def _h_requirements_select_one(cur, params):
    row = cur.db["requirements"].get(params[0])
    cur._result = [{"data": deepcopy(row)}] if row else []


def _h_requirements_update(cur, params):
    lifecycle_status, data, req_id = params
    if req_id in cur.db["requirements"]:
        cur.db["requirements"][req_id] = deepcopy(_unwrap(data))


def _h_rechunk_insert(cur, params):
    (entry,) = params
    cur.db.setdefault("rechunk_queue", []).append(deepcopy(_unwrap(entry)))


def _h_requirements_select_all(cur, params):
    rows = sorted(cur.db["requirements"].items(), key=lambda kv: kv[0])
    cur._result = [{"data": deepcopy(v)} for _, v in rows]


def _h_locks_select_conflicts(cur, params):
    paths, task_id = params
    cur._result = [
        {"path": path, "task_id": tid}
        for path, tid in cur.db["task_locks"].items()
        if path in paths and tid != task_id
    ]


def _h_locks_upsert(cur, params):
    path, task_id = params
    cur.db["task_locks"][path] = task_id


def _h_locks_delete(cur, params):
    (task_id,) = params
    for path in [p for p, t in cur.db["task_locks"].items() if t == task_id]:
        del cur.db["task_locks"][path]


def _h_locks_select_by_task(cur, params):
    (task_id,) = params
    cur._result = [
        {"path": p} for p, t in sorted(cur.db["task_locks"].items()) if t == task_id
    ]


def _h_locks_select_all(cur, params):
    cur._result = [{"path": p, "task_id": t} for p, t in cur.db["task_locks"].items()]


def _h_tasks_select_one(cur, params):
    row = cur.db["tasks"].get(params[0])
    cur._result = [{"data": deepcopy(row)}] if row else []


def _h_tasks_upsert(cur, params):
    task_id, status, data, updated_at = params
    cur.db["tasks"][task_id] = deepcopy(_unwrap(data))


def _h_tasks_select_all(cur, params):
    rows = sorted(cur.db["tasks"].items(), key=lambda kv: kv[0])
    cur._result = [{"data": deepcopy(v)} for _, v in rows]


def _h_tasks_select_like(cur, params):
    prefix = params[0].rstrip("%")
    cur._result = [
        {"task_id": tid} for tid in cur.db["tasks"] if tid.startswith(prefix)
    ]


def _h_tasks_update(cur, params):
    status, data, updated_at, task_id = params
    if task_id in cur.db["tasks"]:
        cur.db["tasks"][task_id] = deepcopy(_unwrap(data))


_HANDLERS = {
    "SELECT project_id, status, data FROM projects ORDER BY project_id": _h_projects_select_all,
    "SELECT project_id FROM projects": _h_projects_select_ids,
    "INSERT INTO projects (project_id, status, data) VALUES (%s, %s, %s)": _h_projects_insert,
    "SELECT status, data FROM projects WHERE project_id = %s": _h_projects_select_one,
    "UPDATE projects SET status = %s WHERE project_id = %s": _h_projects_update_status,
    "INSERT INTO projects (project_id, status, data) VALUES (%s, %s, %s) ON CONFLICT (project_id) DO UPDATE SET data = EXCLUDED.data": _h_projects_upsert,
    "SELECT req_id FROM requirements WHERE req_id LIKE %s": _h_requirements_select_like,
    "INSERT INTO requirements (req_id, doc_type_code, area_code, lifecycle_status, data) VALUES (%s, %s, %s, %s, %s)": _h_requirements_insert,
    "SELECT data FROM requirements WHERE req_id = %s": _h_requirements_select_one,
    "UPDATE requirements SET lifecycle_status = %s, data = %s WHERE req_id = %s": _h_requirements_update,
    "INSERT INTO rechunk_queue (entry) VALUES (%s)": _h_rechunk_insert,
    "SELECT data FROM requirements ORDER BY req_id": _h_requirements_select_all,
    "SELECT path, task_id FROM task_locks WHERE path = ANY(%s) AND task_id != %s": _h_locks_select_conflicts,
    "INSERT INTO task_locks (path, task_id) VALUES (%s, %s) ON CONFLICT (path) DO UPDATE SET task_id = EXCLUDED.task_id": _h_locks_upsert,
    "DELETE FROM task_locks WHERE task_id = %s": _h_locks_delete,
    "SELECT path FROM task_locks WHERE task_id = %s ORDER BY path": _h_locks_select_by_task,
    "SELECT path, task_id FROM task_locks": _h_locks_select_all,
    "SELECT data FROM tasks WHERE task_id = %s": _h_tasks_select_one,
    "INSERT INTO tasks (task_id, status, data, updated_at) VALUES (%s, %s, %s, %s) ON CONFLICT (task_id) DO UPDATE SET status = EXCLUDED.status, data = EXCLUDED.data, updated_at = EXCLUDED.updated_at": _h_tasks_upsert,
    "SELECT data FROM tasks ORDER BY task_id": _h_tasks_select_all,
    "SELECT task_id FROM tasks WHERE task_id LIKE %s": _h_tasks_select_like,
    "UPDATE tasks SET status = %s, data = %s, updated_at = %s WHERE task_id = %s": _h_tasks_update,
}


class FakeConnection:
    """세션 범위 인메모리 "테이블" 저장소 — commit/rollback은 no-op(단일 fake 트랜잭션)."""

    def __init__(self):
        self.db = {
            "projects": {},
            "requirements": {},
            "task_locks": {},
            "tasks": {},
            "rechunk_queue": [],
        }
        self.committed = 0

    def cursor(self):
        return FakeCursor(self.db)

    def commit(self):
        self.committed += 1

    def rollback(self):
        pass
