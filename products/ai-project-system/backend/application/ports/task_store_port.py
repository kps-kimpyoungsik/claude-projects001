"""태스크 저장소 표준 포트 (§2-3, T102 NTM).

`backend.adapters.persistence.task_store.TaskStore`가 실제로 구현하는 public 메서드
시그니처를 그대로 추출한 것 — 새 패턴 발명이 아니라 `db_port.py`/`parser_port.py`와
같은 기존 포트 패턴을 미적용 영역까지 넓힌 것이다(CRZ).
"""

from abc import ABC, abstractmethod

from backend.domain.entities.task import Task


class TaskStorePort(ABC):
    @abstractmethod
    def create_or_update(self, task: Task, graph: dict | None = None) -> Task:
        pass

    @abstractmethod
    def get(self, task_id: str) -> Task | None:
        pass

    @abstractmethod
    def list_all(self) -> list[Task]:
        pass

    @abstractmethod
    def check_all_conflicts(self) -> dict:
        pass
