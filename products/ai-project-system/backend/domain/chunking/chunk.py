"""[Phase 2] Chunk 데이터클래스 + 전역 맥락 강화.

헥사고날 리팩토링(2026-07-19)으로 `backend/domain/chunk.py`에서 분리했다 — Chunk 엔티티와
전역 맥락 삽입은 순수 데이터 로직, 실제 분할 전략(HeadingBoundarySplitter 등)은
`backend/domain/chunking/heading_splitter.py`로 나눴다(CRZ, 재복제 없음).
"""

from dataclasses import dataclass, field


@dataclass
class Chunk:
    chunk_id: str
    content: str
    parent_id: str | None = None
    global_context: dict = field(default_factory=dict)
    # plans/_plan/02_PHASE2_ORCHESTRATION_PREVIEW.md §1-2 SourceLocation — "이 청크가 원본
    # 문서 어디서 나왔는가"를 미리보기가 하이라이트할 수 있도록 좌표를 함께 들고 다닌다.
    doc_id: str = ""
    heading_path: list[str] = field(default_factory=list)
    char_start: int | None = None
    char_end: int | None = None
    # plans/_plan/08_RECORDING_STT_STRATEGY.md §2 — 녹음(오디오) 전용 좌표.
    # 02_PHASE2_ORCHESTRATION_PREVIEW.md §1-2에서 "3차 이후 별도 착수 단위"로 미뤄뒀던
    # timestamp_start_ms/timestamp_end_ms를 이번 착수 단위에서 채운다. 텍스트 포맷 청크는
    # None으로 남는다(포맷별 선택적 좌표 — §1-2 설계 그대로).
    timestamp_start_ms: int | None = None
    timestamp_end_ms: int | None = None


def inject_global_context(chunk: Chunk, context_label: str) -> Chunk:
    """자식 청크 본문 맨 앞에 전역 맥락 헤더를 강제 삽입한다.

    예: "[전역 맥락: 2026-07-17 프로젝트 X의 결제 시스템 보안 정책]"
    검색 시 문맥 소실을 막기 위한 것으로, 원본 content는 변경하지 않고
    반환 시에만 헤더를 붙인다 (원본 무결성 보존 — T90 DELP 계열 원칙).
    """
    header = f"[전역 맥락: {context_label}]\n\n"
    enriched = Chunk(
        chunk_id=chunk.chunk_id,
        content=header + chunk.content,
        parent_id=chunk.parent_id,
        global_context={**chunk.global_context, "label": context_label},
        # 위치정보(§1-2)는 헤더 삽입과 무관하게 원본 그대로 보존 — 안 넣으면 미리보기가
        # 하이라이트할 좌표를 잃어버린다(실측 없이 조용히 사라지는 버그, 여기서 직접 확인).
        doc_id=chunk.doc_id,
        heading_path=chunk.heading_path,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        timestamp_start_ms=chunk.timestamp_start_ms,
        timestamp_end_ms=chunk.timestamp_end_ms,
    )
    return enriched
