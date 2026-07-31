"""청킹 위치추적(§1-2 SourceLocation) 회귀 테스트.

test_document_store_roundtrip_preserves_char_offsets는 이번 세션에서 실제로 발견한
버그(Windows에서 Path.write_text 기본 동작이 \\n -> \\r\\n 치환 -> 미리보기 하이라이트가
밀리는 문제)의 재발 방지 테스트다 — 이 테스트가 실패하면 그 버그가 돌아온 것이다.
"""

from backend.domain.requirements.classifier import classify_chunk
from backend.domain.chunking.chunk import Chunk, inject_global_context
from backend.domain.chunking.heading_splitter import SPCEngine
from backend.adapters.persistence.document_store import DocumentStore

DOC = (
    "# 사업 개요\n"
    "본 제안서는 결제 시스템 구축 사업계획서를 기반으로 한다.\n\n"
    "# 보안 요건\n"
    "암호화 솔루션과 SSL 인증서를 적용하고 소스코드 취약성 점검을 수행한다.\n"
)


def test_split_with_spans_offsets_match_original_string():
    splitter = SPCEngine().__dict__["_splitter"]
    sections = splitter.split_with_spans(DOC)
    assert len(sections) == 2
    for section in sections:
        slice_ = DOC[section["char_start"]:section["char_end"]]
        assert slice_.strip() == section["content"]


def test_process_document_children_carry_location_fields():
    engine = SPCEngine()
    chunks = engine.process_document(DOC, context_label="테스트 문서", doc_id="doc1")
    children = [c for c in chunks if c.parent_id is not None]
    assert len(children) == 2
    for child in children:
        assert child.doc_id == "doc1"
        assert child.char_start is not None
        assert child.char_end is not None
        assert child.heading_path  # 비어있지 않아야 함


def test_document_store_roundtrip_preserves_char_offsets(tmp_path):
    """회귀 테스트 — Windows CRLF 치환 버그(2026-07-19 발견·수정) 재발 방지.

    DocumentStore.save()가 개행을 있는 그대로 보존하지 못하면(newline="" 없이 쓰면),
    저장된 파일의 길이가 원본과 달라져 char_start/char_end가 더 이상 맞지 않는다.
    """
    store = DocumentStore(tmp_path / "documents")
    store.save("doc1", DOC)
    loaded = store.load("doc1")
    assert loaded == DOC  # 바이트 단위로 원본과 동일해야 오프셋이 유지됨
    assert "\r\n" not in open(tmp_path / "documents" / "doc1.md", "rb").read().decode("utf-8")


def test_full_pipeline_offsets_survive_disk_roundtrip(tmp_path):
    """청킹 -> 저장 -> 재로드 후에도 char_start:char_end 슬라이스가 정확해야 한다
    (미리보기 화면이 실제로 하는 것과 동일한 경로 — end-to-end 회귀)."""
    engine = SPCEngine()
    chunks = engine.process_document(DOC, context_label="테스트 문서", doc_id="doc1")
    children = [c for c in chunks if c.parent_id is not None]

    store = DocumentStore(tmp_path / "documents")
    store.save("doc1", DOC)
    reloaded = store.load("doc1")

    for child in children:
        slice_ = reloaded[child.char_start:child.char_end]
        assert slice_.lstrip().startswith("#"), f"오프셋이 헤딩에서 시작하지 않음: {slice_[:20]!r}"


def test_classifier_still_works_on_located_chunk_content():
    engine = SPCEngine()
    chunks = engine.process_document(DOC, context_label="테스트 문서", doc_id="doc1")
    sec_chunk = next(c for c in chunks if c.heading_path == ["보안 요건"])
    result = classify_chunk(sec_chunk.content)
    assert result.area_code == "SEC"


def test_chunk_default_timestamp_fields_are_none_for_text_documents():
    """텍스트 문서 청크는 timestamp_*_ms가 None으로 남아야 한다 (§1-2 포맷별 선택적 좌표,
    plans/_plan/08_RECORDING_STT_STRATEGY.md 신규 필드의 기존 경로 회귀 방지)."""
    chunk = Chunk(chunk_id="doc1::child:0", content="본문")
    assert chunk.timestamp_start_ms is None
    assert chunk.timestamp_end_ms is None


def test_nested_subheading_isolates_table_from_prose_chunk():
    """[2026-07-22 청킹 방법론 재검토] pptx/pdf 어댑터가 "### Table N (...)" 서브헤딩으로
    표를 슬라이드/페이지 본문과 분리하는 근거 — HeadingBoundarySplitter가 실제로 `##`와 `###`를
    별개 경계로 나누고, heading_path에 부모 헤딩(Slide 1)이 남는지 확인한다(2026 RAG 청킹
    모범사례: 표는 프로즈와 섞인 채로 두지 않고 별도 청크로 분리해야 함, 외부 조사 근거)."""
    doc = (
        "## Slide 1\n"
        "발표 본문 텍스트\n\n"
        "### Table 1 (Slide 1)\n"
        "| Header1 | Header2 |\n"
        "| --- | --- |\n"
        "| Val1 | Val2 |\n"
    )
    splitter = SPCEngine().__dict__["_splitter"]
    sections = splitter.split_with_spans(doc)

    assert len(sections) == 2
    prose, table = sections[0], sections[1]
    assert "발표 본문 텍스트" in prose["content"]
    assert "Header1" not in prose["content"]  # 표가 본문 청크에 섞이지 않음
    assert "Val1" in table["content"]
    assert table["heading_path"] == ["Slide 1", "Table 1 (Slide 1)"]


def test_inject_global_context_preserves_timestamp_fields():
    chunk = Chunk(
        chunk_id="doc1::segment:0",
        content="발화 내용",
        doc_id="doc1",
        timestamp_start_ms=0,
        timestamp_end_ms=2500,
    )
    enriched = inject_global_context(chunk, "테스트 녹음")
    assert enriched.timestamp_start_ms == 0
    assert enriched.timestamp_end_ms == 2500


# [2026-07-31 커버리지 보완] 아래는 지금까지 split_with_spans()만 간접 사용돼 실행되지 않던
# 분기들이다 — HeadingBoundarySplitter.split()(레거시 단순 API), SemanticBoundarySplitter의
# judge 실패 폴백, 빈 섹션 스킵, SPCEngine의 split_with_spans 미지원 splitter 폴백 경로.


def test_heading_boundary_splitter_plain_split_returns_section_strings():
    """HeadingBoundarySplitter.split()(위치정보 없는 단순 API)이 여전히 올바르게 동작하는지
    직접 검증 — split_with_spans()와 동일한 섹션 경계를 문자열 리스트로 반환해야 한다."""
    from backend.domain.chunking.heading_splitter import HeadingBoundarySplitter

    splitter = HeadingBoundarySplitter()
    sections = splitter.split(DOC)
    assert len(sections) == 2
    assert sections[0].startswith("# 사업 개요")
    assert sections[1].startswith("# 보안 요건")


def test_heading_boundary_splitter_plain_split_empty_markdown_returns_empty_list():
    from backend.domain.chunking.heading_splitter import HeadingBoundarySplitter

    assert HeadingBoundarySplitter().split("   \n\t  ") == []


def test_semantic_boundary_splitter_falls_back_when_judge_raises():
    """[T99 AIOS 우아한 성능저하] judge.judge()가 예외를 던지면(서비스 다운 등) heading 기준
    분할 결과만 정직하게 반환한다 — 파이프라인을 막지 않는다."""
    from backend.domain.chunking.heading_splitter import SemanticBoundarySplitter

    class _BrokenJudge:
        def judge(self, sections):
            raise RuntimeError("judge 서비스 다운 시뮬레이션")

    splitter = SemanticBoundarySplitter(judge=_BrokenJudge())
    sections = splitter.split_with_spans(DOC)
    assert len(sections) == 2
    for s in sections:
        assert s["relationships"] == []  # 관계 판단 없이 폴백


def test_split_with_spans_skips_leading_whitespace_only_section():
    """[Line 134] 첫 헤딩 이전에 공백 줄만 있으면(내용 없는 선행 섹션) 결과에서 제외된다."""
    from backend.domain.chunking.heading_splitter import HeadingBoundarySplitter

    doc = "\n\n# 섹션1\n본문\n"
    sections = HeadingBoundarySplitter().split_with_spans(doc)
    assert len(sections) == 1
    assert sections[0]["heading_path"] == ["섹션1"]


def test_spc_engine_falls_back_to_plain_split_when_splitter_lacks_span_support():
    """[Line 173] splitter가 split_with_spans()를 지원하지 않는 구식 객체여도(hasattr 검사
    실패) SPCEngine이 plain split()으로 폴백해 정상 동작해야 한다."""
    class _LegacySplitterWithoutSpans:
        def split(self, markdown):
            return [s.strip() for s in markdown.split("\n\n") if s.strip()]

    engine = SPCEngine(splitter=_LegacySplitterWithoutSpans())
    chunks = engine.process_document(DOC, context_label="테스트", doc_id="doc1")
    children = [c for c in chunks if c.parent_id is not None]
    assert len(children) == 2
    for child in children:
        assert child.char_start is None  # 구식 splitter는 위치정보를 못 주므로 None 유지
        assert child.char_end is None
