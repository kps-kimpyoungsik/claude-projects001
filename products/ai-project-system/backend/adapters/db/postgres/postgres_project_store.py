"""`ProjectStorePort`의 PostgreSQL 구현체 (2026-07-24 신설).

⚠ 검증 미확정 — 실제 PostgreSQL로 연결·CRUD 테스트를 거치지 않았다(README.md 참조,
평식 지시 2026-07-24 "코드만 작성, 검증은 미확정으로 명시"). `project_registry.py`(JSON
어댑터)와 완전히 동일한 공개 API·동작(DEFAULT_PROJECT_ID 가상 프로젝트, PROJECT_STATUSES
검증)을 제공하도록 작성했으나, 실제 PostgreSQL 서버 없이는 SQL 구문 오류·타입 불일치
가능성을 배제할 수 없다.
"""

from datetime import datetime, timezone

from backend.adapters.db.postgres.connection import get_connection
from backend.adapters.persistence.project_registry import (
    DEFAULT_PROJECT_ID,
    DEFAULT_PROJECT_NAME,
    PROJECT_STATUSES,
    ProjectValidationError,
)
from backend.application.ports.project_store_port import ProjectStorePort
from backend.domain.entities.project import Project


def _to_project(row: dict) -> Project:
    return Project(
        id=row["project_id"],
        name=row["data"]["name"],
        status=row["status"],
        created_at=datetime.fromisoformat(row["data"]["created_at"]),
    )


class PostgresProjectStore(ProjectStorePort):
    def __init__(self, conn=None):
        self._conn = conn  # 테스트 시 주입 가능(미확정 상태 — 실제 연결은 get_connection() 참조)

    def _connection(self):
        return self._conn or get_connection()

    def list_all(self) -> list[Project]:
        conn = self._connection()
        with conn.cursor() as cur:
            cur.execute("SELECT project_id, status, data FROM projects ORDER BY project_id")
            rows = cur.fetchall()
        projects = [_to_project(r) for r in rows]
        if not any(p.id == DEFAULT_PROJECT_ID for p in projects):
            # JSON 어댑터(ProjectRegistry.list_all())와 동일하게, DEFAULT_PROJECT_ID는
            # 레코드가 없어도 항상 가상으로 존재한다(하위호환 무마이그레이션 원칙).
            projects.insert(
                0,
                Project(
                    id=DEFAULT_PROJECT_ID, name=DEFAULT_PROJECT_NAME,
                    status="IMPLEMENTING", created_at=datetime.now(timezone.utc),
                ),
            )
        return projects

    def get(self, project_id: str) -> Project | None:
        for project in self.list_all():
            if project.id == project_id:
                return project
        return None

    def create(self, name: str) -> Project:
        name = name.strip()
        if not name:
            raise ProjectValidationError("프로젝트명은 비어 있을 수 없습니다")

        conn = self._connection()
        with conn.cursor() as cur:
            cur.execute("SELECT project_id FROM projects")
            existing_ids = {r["project_id"] for r in cur.fetchall()} | {DEFAULT_PROJECT_ID}
            seq = len(existing_ids)
            project_id = f"proj-{seq:03d}"
            while project_id in existing_ids:
                seq += 1
                project_id = f"proj-{seq:03d}"

            project = Project(
                id=project_id, name=name, status="IMPLEMENTING",
                created_at=datetime.now(timezone.utc),
            )
            data = {"id": project.id, "name": project.name, "created_at": project.created_at.isoformat()}
            cur.execute(
                "INSERT INTO projects (project_id, status, data) VALUES (%s, %s, %s)",
                (project.id, project.status, psycopg2_json(data)),
            )
        conn.commit()
        return project

    def update_status(self, project_id: str, status: str) -> Project:
        if status not in PROJECT_STATUSES:
            raise ProjectValidationError(
                f"허용되지 않는 상태입니다: {status} (허용: {sorted(PROJECT_STATUSES)})"
            )

        conn = self._connection()
        with conn.cursor() as cur:
            cur.execute("SELECT status, data FROM projects WHERE project_id = %s", (project_id,))
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE projects SET status = %s WHERE project_id = %s", (status, project_id)
                )
                conn.commit()
                return Project(
                    id=project_id, name=row["data"]["name"], status=status,
                    created_at=datetime.fromisoformat(row["data"]["created_at"]),
                )

            if project_id == DEFAULT_PROJECT_ID:
                # DEFAULT_PROJECT_ID는 list_all()에서만 가상으로 존재할 수 있다 — 상태를
                # 실제로 바꾸려면 이 시점에 행으로 구체화(materialize)한다(JSON 어댑터와 동일).
                project = Project(
                    id=DEFAULT_PROJECT_ID, name=DEFAULT_PROJECT_NAME,
                    status=status, created_at=datetime.now(timezone.utc),
                )
                data = {"id": project.id, "name": project.name, "created_at": project.created_at.isoformat()}
                cur.execute(
                    "INSERT INTO projects (project_id, status, data) VALUES (%s, %s, %s)",
                    (project.id, project.status, psycopg2_json(data)),
                )
                conn.commit()
                return project

        raise ProjectValidationError(f"존재하지 않는 프로젝트입니다: {project_id}")


def psycopg2_json(data: dict):
    """psycopg2가 dict를 JSONB 파라미터로 바인딩할 수 있도록 감싼다(지연 import —
    이 모듈 전체를 psycopg2 미설치 환경에서도 최소한 읽을 수 있게, connection.py만 필수 의존)."""
    from psycopg2.extras import Json
    return Json(data)
