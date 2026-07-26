"""[2026-07-22 고도화] 다중 프로젝트 레지스트리 — "시작부터 프로젝트 1개만 관리되면 안 된다"
(사용자 지시)를 실제로 구현한다.

기존 `backend/domain/entities/project.py`의 `Project` dataclass(id/name/status/created_at)를
그대로 재사용한다(CRZ — 신규 엔티티 발명 없음, 이 엔티티는 지금까지 정의만 되고 실제로
쓰이지 않았다). `ProjectConfigStore`(project_config_store.py)는 프로젝트 1건의 "분야·문서유형
선택 마법사" 세부 설정을 담당하는 별개 모듈로 남겨둔다 — 이번 변경은 그 모듈을 건드리지
않는다(CRZ, 기존 계약 불변, 향후 병합 여지는 있으나 이번 범위 밖).

**하위호환(무마이그레이션) 원칙**: 레지스트리가 비어 있어도(신규 설치·이번 세션 이전 데이터)
`DEFAULT_PROJECT_ID`("default")는 항상 가상으로 존재한다 — 지금까지 쌓인 `data/
requirements_store.json` 등 기존 데이터가 그대로 "기본 프로젝트"로 보이며, 별도 이관
스크립트가 필요 없다. 새 프로젝트만 `data/projects/{project_id}/` 아래 격리된다
(project_scope.py의 `resolve_project_data_dir()`가 이 경로 규칙의 유일한 SSOT).
"""

import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from backend.application.ports.project_store_port import ProjectStorePort
from backend.domain.entities.project import Project

DEFAULT_PROJECT_ID = "default"
DEFAULT_PROJECT_NAME = "기본 프로젝트"

# `backend/domain/entities/project.py`의 `status` 필드 주석(WAITING/IMPLEMENTING/VERIFIED)을
# 실제로 강제하는 값 집합 — 지금까지 이 필드는 생성 시 "IMPLEMENTING"으로 고정될 뿐 전이
# 수단이 전혀 없었다(2026-07-23 실측 확인: projects_api.py에 상태 변경 엔드포인트 없음).
# [2026-07-26 고도화] ON_HOLD(보류)·ARCHIVED(삭제 — soft-delete, 물리 삭제 금지) 추가.
# ARCHIVED는 "삭제" 의미의 상태 라벨일 뿐이며, 레코드 자체는 그대로 파일에 남는다 — 기본
# 활성 뷰(list_all 등)에서 제외하는 필터링은 호출부(향후 프런트/트랙)의 책임으로 남긴다
# (이번 변경 범위는 상태값 허용까지 — 과잉 확장 금지, T98 AIP).
PROJECT_STATUSES = {"WAITING", "IMPLEMENTING", "VERIFIED", "ON_HOLD", "ARCHIVED"}

# [2026-07-26 고도화] start_date/end_date 형식 검증 — "YYYY-MM-DD" ISO 날짜 문자열만 허용.
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_date(label: str, value: str | None) -> None:
    if value is None:
        return
    if not _DATE_RE.fullmatch(value):
        raise ProjectValidationError(f"{label} 형식이 올바르지 않습니다(YYYY-MM-DD 필요): {value!r}")


class ProjectValidationError(ValueError):
    pass


def _to_record(project: Project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "status": project.status,
        "created_at": project.created_at.isoformat(),
        "start_date": project.start_date,
        "end_date": project.end_date,
    }


def _from_record(record: dict) -> Project:
    # [2026-07-26 고도화] start_date/end_date는 이 필드가 생기기 전 저장된 기존 레코드에는
    # 아예 키가 없다 — `.get(..., None)`으로 하위호환(구 레코드는 두 필드 모두 None으로
    # 로드되고, 이는 도메인 엔티티의 기본값과 동일해 즉시 재저장해도 회귀 없음).
    return Project(
        id=record["id"],
        name=record["name"],
        status=record["status"],
        created_at=datetime.fromisoformat(record["created_at"]),
        start_date=record.get("start_date"),
        end_date=record.get("end_date"),
    )


class ProjectRegistry(ProjectStorePort):
    """`ProjectStorePort`의 JSON 파일 구현체 — 여러 `Project`를 JSON 파일 1개에 목록으로
    관리한다(기존 RequirementStore/TaskStore와 동일한 "단일 JSON 파일 read-modify-write"
    패턴 재사용, CRZ — 신규 저장기술 발명 없음).

    PostgreSQL 등으로 교체 시 이 클래스처럼 `ProjectStorePort`를 구현하는 새 어댑터만
    작성하면 되고, 호출부(`projects_api.py`)만 바꾸면 된다."""

    def __init__(self, store_path: Path):
        self._path = store_path

    def _load_raw(self) -> list[dict]:
        if not self._path.exists():
            return []
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _save_raw(self, records: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_all(self) -> list[Project]:
        records = self._load_raw()
        projects = [_from_record(r) for r in records]
        if not any(p.id == DEFAULT_PROJECT_ID for p in projects):
            projects.insert(
                0,
                Project(
                    id=DEFAULT_PROJECT_ID,
                    name=DEFAULT_PROJECT_NAME,
                    status="IMPLEMENTING",
                    created_at=datetime.now(timezone.utc),
                ),
            )
        return projects

    def get(self, project_id: str) -> Project | None:
        for project in self.list_all():
            if project.id == project_id:
                return project
        return None

    def create(
        self,
        name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Project:
        name = name.strip()
        if not name:
            raise ProjectValidationError("프로젝트명은 비어 있을 수 없습니다")
        _validate_date("start_date", start_date)
        _validate_date("end_date", end_date)

        records = self._load_raw()
        existing_ids = {r["id"] for r in records} | {DEFAULT_PROJECT_ID}
        seq = len(records) + 1
        project_id = f"proj-{seq:03d}"
        while project_id in existing_ids:
            seq += 1
            project_id = f"proj-{seq:03d}"

        project = Project(
            id=project_id,
            name=name,
            status="IMPLEMENTING",
            created_at=datetime.now(timezone.utc),
            start_date=start_date,
            end_date=end_date,
        )
        records.append(_to_record(project))
        self._save_raw(records)
        return project

    def update_status(self, project_id: str, status: str) -> Project:
        """상태 전이(WAITING/IMPLEMENTING/VERIFIED) — 지금까지 `create()`가 고정값
        "IMPLEMENTING"으로만 만들고 그 뒤 바꿀 수단이 없던 기능 갭을 메운다(2026-07-23
        고도화 후속). Task.status의 `task_state_machine.py`처럼 정교한 전이 그래프까지는
        아니고, 우선 "허용된 값인지"만 검증한다(범위 축소 — 순서 규칙까지는 이번에 다루지
        않음, 과장 금지)."""
        if status not in PROJECT_STATUSES:
            raise ProjectValidationError(
                f"허용되지 않는 상태입니다: {status} (허용: {sorted(PROJECT_STATUSES)})"
            )

        records = self._load_raw()
        for record in records:
            if record["id"] == project_id:
                record["status"] = status
                self._save_raw(records)
                return _from_record(record)

        if project_id == DEFAULT_PROJECT_ID:
            # DEFAULT_PROJECT_ID는 list_all()에서만 가상으로 존재하고 파일엔 없을 수
            # 있다 — 상태를 실제로 바꾸려면 이 시점에 파일로 구체화(materialize)한다.
            project = Project(
                id=DEFAULT_PROJECT_ID, name=DEFAULT_PROJECT_NAME,
                status=status, created_at=datetime.now(timezone.utc),
            )
            records.append(_to_record(project))
            self._save_raw(records)
            return project

        raise ProjectValidationError(f"존재하지 않는 프로젝트입니다: {project_id}")

    def update_fields(
        self,
        project_id: str,
        name: str | None = None,
        start_date: str | None = ...,
        end_date: str | None = ...,
    ) -> Project:
        """[2026-07-26 고도화] `name`/`start_date`/`end_date`만 갱신하는 부분 업데이트 —
        `status`는 `update_status()`가 이미 전담하므로 이 메서드는 건드리지 않는다(단일
        책임 유지, CRZ). `start_date`/`end_date`는 "값을 지정하지 않음"(그대로 유지)과
        "명시적으로 null로 지움"을 구분해야 하므로 sentinel(`...`)을 기본값으로 쓴다 —
        `None`을 기본값으로 두면 "지우기"와 "미지정"을 구분할 수 없다."""
        if name is not None:
            name = name.strip()
            if not name:
                raise ProjectValidationError("프로젝트명은 비어 있을 수 없습니다")
        if start_date is not ...:
            _validate_date("start_date", start_date)
        if end_date is not ...:
            _validate_date("end_date", end_date)

        records = self._load_raw()
        for record in records:
            if record["id"] == project_id:
                if name is not None:
                    record["name"] = name
                if start_date is not ...:
                    record["start_date"] = start_date
                if end_date is not ...:
                    record["end_date"] = end_date
                self._save_raw(records)
                return _from_record(record)

        if project_id == DEFAULT_PROJECT_ID:
            # update_status()와 동일한 materialize 패턴 — DEFAULT는 파일에 없을 수 있다.
            base = Project(
                id=DEFAULT_PROJECT_ID, name=DEFAULT_PROJECT_NAME,
                status="IMPLEMENTING", created_at=datetime.now(timezone.utc),
            )
            if name is not None:
                base.name = name
            if start_date is not ...:
                base.start_date = start_date
            if end_date is not ...:
                base.end_date = end_date
            records.append(_to_record(base))
            self._save_raw(records)
            return base

        raise ProjectValidationError(f"존재하지 않는 프로젝트입니다: {project_id}")
