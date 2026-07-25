"""[Phase 2] 문서 파서 표준 포트.

`db_port.py`와 동일 위치(`backend/application/ports/`)에 둔다 — 2026-07-19 헥사고날
리팩토링으로 (구)`core_was_block/application/ports`에서 이곳으로 이동했다. 별도 트리를
만들지 않고 기존 포트 트리 안에 통합 유지한다(CRZ — 구조 중복 방지).
"""

from abc import ABC, abstractmethod
from typing import Any, BinaryIO


class ParserPort(ABC):
    @abstractmethod
    def can_handle(self, file_extension: str) -> bool:
        pass

    @abstractmethod
    def parse_to_markdown(self, file_stream: BinaryIO, metadata: dict[str, Any]) -> str:
        """입력 바이너리를 정규화된 마크다운으로 변환한다.

        무결성 검증(변환 규칙 확인)은 이 메서드 내부에서 하드코딩하지 않는다 —
        호출자가 `governance/workflows/RECALL_UNIVERSAL_SEARCH_GUIDE.md` 절차에 따라
        착수 전 `/recall <FILE_INTEGRITY_POLICY>`를 실행하는 것을 전제한다(관심사 분리).
        """
        pass
