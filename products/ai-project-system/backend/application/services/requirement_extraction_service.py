"""[Phase 2 x Phase 3 연결] SPC 청크 → 요구사항 자동 분류·채번 파이프라인.

00_PROJECT_CONSTITUTION.md §1 핵심 목표의 마지막 빠진 조각을 잇는다:
청킹(backend/domain/chunk.py) → **이 모듈** → 분류·채번(backend.domain.classifier
+ requirement_store) → 그래프 등록(backend.domain.id_format, 후속 단계에서 연결).

parent 청크(SPCEngine이 만드는 문서 전체 요약 발췌)는 요구사항 단위가 아니므로 제외한다.
"""

from backend.domain.requirements.classifier import classify_chunk
from backend.adapters.persistence.requirement_store import RequirementRecord, RequirementStore
from backend.domain.chunking.chunk import Chunk


def extract_requirements_from_chunks(
    chunks: list[Chunk], store: RequirementStore, doc_format: str = "",
    pdf_source: bytes | str | None = None,
) -> list[RequirementRecord]:
    """자식 청크만 분류 대상으로 삼아 요구사항 항목을 채번·저장한다.

    분류 실패(문서유형·영역 둘 다 매칭 없음) 청크는 조용히 버리지 않고 반환값에서
    빠지는 것으로 표시된다 — 호출자는 `len(chunks) - 1(parent 제외) - len(결과)`로
    "분류 안 된 청크 수"를 셀 수 있다(과장 없이 정직하게 누락 파악 가능).

    doc_format(예: ".png")이 이미지 포맷이면 이 문서에서 나온 요구사항 전부에
    source_is_image=True를 표시한다 — 실제 이미지 분석(OCR/비전)은 아직 미구현이라
    "출처가 이미지인데 분석은 안 됨"을 정직하게 표시하는 용도(과장 금지, T98 AIP).

    plans/_plan/02_PHASE2_ORCHESTRATION_PREVIEW.md §8 — doc_format이 PDF이고 원본 PDF
    바이트/경로(`pdf_source`)가 주어지면, 레코드 생성 직전에 `pdf_bbox_adapter.locate()`로
    `page_number`/`bbox`를 채운다. PDF가 아니거나 `pdf_source`가 없으면(호출자가 아직 배선
    안 했거나 원본을 들고 있지 않은 경로) 두 필드는 기존 그대로 None으로 남는다(§8-3
    하위호환, 회귀 없음).

    **정직성 한계(T98 AIP)**: `pdf_bbox_adapter.locate()`는 이 모듈 자신의 텍스트 재구성
    (`extract_text()`, PyMuPDF 기반) 기준 오프셋으로 페이지/bbox를 찾는다. 그런데
    `char_start`/`char_end`는 실제로는 `PdfParserAdapter`(pdfplumber 기반, `pdf_adapter.py`)가
    만든 마크다운 기준 오프셋이다 — 두 추출 엔진의 텍스트가 완전히 문자 단위로 동일하다는
    보장은 없으므로(표가 있거나 공백 처리가 다른 페이지), bbox/page_number는 "최선의 근사"이지
    100% 정밀 보장은 아니다. 매칭 실패 시 `locate()`가 정직하게 `(None, None)`을 돌려주며,
    이 경우 레코드는 그대로 두 필드 모두 None(§8-6 폴백 원칙과 동일하게 preview.html이 텍스트
    하이라이트로 자동 폴백한다).
    """
    source_is_image = doc_format.lower() in {".png", ".jpg", ".jpeg"}
    is_pdf = doc_format.lower() == ".pdf"
    locate_fn = None
    if is_pdf and pdf_source is not None:
        from backend.adapters.parsers.pdf_bbox_adapter import locate as locate_fn  # noqa: E402
    child_chunks = [c for c in chunks if c.parent_id is not None]
    # 2026-07-22 (사용자 지시: "문서 안에서의 관계 판단도 해야 됩니다"): SemanticBoundarySplitter가
    # section index(0,1,2,...) 기준으로 relationships를 부착했다 — child_chunks의 순서가 그
    # 섹션 순서와 동일하므로(SPCEngine.process_document가 enumerate(sections) 순서 그대로
    # child chunk를 만든다, CRZ 재확인) index -> 실제 chunk_id로 안전하게 변환 가능하다.
    chunk_id_by_index = {i: c.chunk_id for i, c in enumerate(child_chunks)}

    records: list[RequirementRecord] = []
    for chunk in chunks:
        if chunk.parent_id is None:
            continue  # parent 청크(문서 전체 요약) 제외
        classification = classify_chunk(chunk.content)
        raw_relationships = chunk.global_context.get("relationships", [])
        related_chunks = [
            {**rel, "to_chunk_id": chunk_id_by_index.get(rel.get("to_index"))}
            for rel in raw_relationships
            if chunk_id_by_index.get(rel.get("to_index")) is not None
        ]
        page_number, bbox = (None, None)
        if locate_fn is not None:
            page_number, bbox = locate_fn(pdf_source, chunk.char_start, chunk.char_end)
        record = store.add_from_classification(
            classification, description=chunk.content, source_ref=chunk.chunk_id,
            doc_id=chunk.doc_id, heading_path=chunk.heading_path,
            char_start=chunk.char_start, char_end=chunk.char_end,
            source_is_image=source_is_image,
            related_chunks=related_chunks,
            page_number=page_number, bbox=bbox,
        )
        if record is not None:
            records.append(record)
    return records
