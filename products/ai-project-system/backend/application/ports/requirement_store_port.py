"""요구사항 저장소 표준 포트 (§2-3, T102 NTM).

`backend.adapters.persistence.requirement_store.RequirementStore`가 실제로 구현하는
public 메서드 시그니처를 그대로 추출한 것 — 새 패턴 발명이 아니라 `db_port.py`/
`parser_port.py`와 같은 기존 포트 패턴을 미적용 영역까지 넓힌 것이다(CRZ). 지금은
JSON 파일 기반 구현(RequirementStore)에 직접 의존하지만, 이 포트가 있어야 나중에
DB 구현으로 교체해도 호출부(application 계층)가 구체 클래스를 몰라도 된다.
"""

from abc import ABC, abstractmethod

from backend.domain.requirements.classifier import ClassificationResult


class RequirementStorePort(ABC):
    @abstractmethod
    def add_from_classification(
        self, classification: ClassificationResult, description: str, source_ref: str,
        doc_id: str = "", heading_path: list | None = None,
        char_start: int | None = None, char_end: int | None = None,
        source_is_image: bool = False,
    ):
        pass

    @abstractmethod
    def set_status(self, req_id: str, status: str, actor: str, reason: str | None = None):
        pass

    @abstractmethod
    def list_all(self) -> list:
        pass

    @abstractmethod
    def request_rechunk(
        self, req_id: str, actor: str, reason: str,
        suggested_char_start: int | None = None, suggested_char_end: int | None = None,
    ):
        pass

    @abstractmethod
    def set_work_status(self, req_id: str, work_status: str, assigned_agent_command: str | None = None):
        pass
