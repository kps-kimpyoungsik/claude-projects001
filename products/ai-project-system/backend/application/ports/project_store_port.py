"""프로젝트 저장소 표준 포트 (§2-3, T102 NTM).

`backend.adapters.persistence.project_registry.ProjectRegistry`가 실제로 구현하는
public 메서드 시그니처를 그대로 추출한 것 — `requirement_store_port.py`/
`task_store_port.py`와 동일한 기존 포트 패턴을 적용한 것이다(CRZ, 신규 패턴 발명 없음).

이 포트가 기존 `backend/adapters/db/sqlite_adapter.py`(`SqliteProjectAdapter`)를
대체한다 — 그 스텁은 `save_project`/`get_project_status`라는, 실제 `ProjectRegistry`
API(list_all/get/create/update_status)와 이름조차 다른 가상의 계약이었고 어디서도
사용되지 않았다(2026-07-23 실측 확인). 지금은 JSON 파일 기반 구현(ProjectRegistry)에
직접 의존하지만, 이 포트가 있어야 나중에 DB 구현(PostgreSQL 등)으로 교체해도 호출부
(`projects_api.py`)가 구체 클래스를 몰라도 된다.
"""

from abc import ABC, abstractmethod

from backend.domain.entities.project import Project


class ProjectStorePort(ABC):
    @abstractmethod
    def list_all(self) -> list[Project]:
        pass

    @abstractmethod
    def get(self, project_id: str) -> Project | None:
        pass

    @abstractmethod
    def create(self, name: str, start_date: str | None = None, end_date: str | None = None) -> Project:
        pass

    @abstractmethod
    def update_status(self, project_id: str, status: str) -> Project:
        pass

    @abstractmethod
    def update_fields(
        self,
        project_id: str,
        name: str | None = None,
        start_date: str | None = ...,
        end_date: str | None = ...,
    ) -> Project:
        pass
