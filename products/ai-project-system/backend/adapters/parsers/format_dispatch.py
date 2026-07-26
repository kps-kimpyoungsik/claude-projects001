"""[Phase 2] 멀티포맷 Ingestion 포맷 디스패치.

[2026-07-26 파일명 변경, CRZ 순수 rename] 옛 파일명 `router.py`가 `backend/adapters/api/*.py`의
FastAPI `APIRouter`(HTTP 라우팅)와 이름이 겹쳐 혼동을 유발했다 — 이 모듈은 HTTP 경로가 아니라
**문서 포맷(확장자)별 처리 전략**을 디스패치한다(완전히 다른 개념). 로직 변경 없음, 유일한
importer(`document_upload_service.py`)와 `technology_extractor.py`의 dotted import 경로,
`tests/test_speech_to_text_adapter.py`의 import만 이 새 경로로 갱신했다.

모든 입력 포맷을 표준 마크다운으로 정규화하는 진입점.
포맷별 실제 파서(HWP/DOCX/PDF/PPTX/이미지)는 `ingestion/parsers/`에 어댑터로 구현하며,
이 라우터는 확장자 → 어댑터 매핑만 담당한다 (Port/Adapter 원칙 — core_was_block과 동일 패턴).

주의: 실제 파싱 엔진(Unstructured, LLM Vision API 등)은 외부 의존성이며 이 스캐폴딩
단계에서는 인터페이스만 정의한다. 각 어댑터는 `NotImplementedError`를 낸다 — 실제
구현은 후속 작업이며, 완료 전 이 파일을 "동작하는 파서"로 착각하지 말 것.
"""

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class NormalizedDocument:
    """Ingestion 결과 — 모든 포맷이 이 형태로 수렴한다."""

    source_path: str
    original_format: str
    markdown: str
    metadata: dict = field(default_factory=dict)


class UnsupportedFormatError(ValueError):
    pass


# 확장자 → 처리 전략 매핑 (설계 명세 그대로)
FORMAT_STRATEGY = {
    ".txt": "text_passthrough",   # 인코딩(UTF-8/EUC-KR) 자동감지 + 텍스트 보존
    ".md": "text_passthrough",
    ".hwp": "unstructured_parse",  # 표는 마크다운 표로 변환
    ".docx": "unstructured_parse",
    ".pdf": "unstructured_parse",
    ".pptx": "slide_parse",        # 슬라이드 단위 분할 + speaker notes 포함
    ".xlsx": "spreadsheet_parse",  # 시트 단위 분할 + 표 마크다운 변환 (2026-07-22 추가)
    ".png": "vision_describe",     # LLM Vision 어댑터로 설명문 변환
    ".jpg": "vision_describe",
    ".jpeg": "vision_describe",
    # plans/_plan/08_RECORDING_STT_STRATEGY.md — 녹음(REC) 문서유형 전용 전략.
    # 02_PHASE2_ORCHESTRATION_PREVIEW.md §1-3에서 예고된 신규 전략명 그대로 사용.
    ".wav": "speech_to_text",
    ".mp3": "speech_to_text",
    ".m4a": "speech_to_text",
}


class IngestionRouter:
    """[2026-07-26 실측 확인] 이 클래스는 현재 미사용 — 실제 업로드는
    `backend/application/services/document_upload_service.py`가 처리한다(확장자별 실제
    파서 호출도 그쪽 경로에서 이뤄짐). 향후 재사용 가능성이 있는 유틸이라 보존만 하며,
    새 어댑터 연결처가 필요할 때 이 클래스를 실제 배차 경로로 승격하려면
    `document_upload_service.py`가 이 `route()`를 호출하도록 바꾸면 된다(현재는 그 연결이
    없다는 사실을 정직하게 남긴다, T98 AIP)."""

    def __init__(self, adapters: dict[str, Callable[[str], NormalizedDocument]] | None = None):
        # adapters: strategy_name -> 실제 파서 함수. 미주입 시 전량 NotImplementedError.
        self._adapters = adapters or {}

    def route(self, file_path: str, ext: str) -> NormalizedDocument:
        ext = ext.lower()
        if ext not in FORMAT_STRATEGY:
            raise UnsupportedFormatError(f"미지원 포맷: {ext}")
        strategy = FORMAT_STRATEGY[ext]
        adapter = self._adapters.get(strategy)
        if adapter is None:
            raise NotImplementedError(
                f"strategy '{strategy}' 어댑터 미구현 — ingestion/parsers/에 구현 후 주입 필요"
            )
        return adapter(file_path)
