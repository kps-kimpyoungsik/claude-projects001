"""[문서 업로드 파이프라인] 업로드된 파일 → 파싱 → 청킹 → 분류·채번 오케스트레이션.

`plans/_plan/09_DOCUMENT_UPLOAD_PIPELINE.md` 설계 그대로 구현한다. 이 모듈이 지금까지
따로 존재하던 조각들(ParserPort 어댑터·SPCEngine·requirement_extraction_service)을 실제로
연결하는 유일한 조립 지점이다 — 새 포맷을 지원하려면 `_ADAPTERS`에 `ParserPort` 구현체를
추가하기만 하면 된다(§4 설계 그대로, CRZ — 새 등록 메커니즘 발명 없음, 리스트 append만).

`router.py`의 `IngestionRouter`(`NormalizedDocument` 계약)는 쓰지 않는다 — 그 계약에
실제로 배선된 어댑터가 하나도 없었다는 것이 이번 설계의 근본원인 진단(§1)이었고, 이미 검증된
`ParserPort` 계약(docx_adapter.py가 실제로 구현·사용 중)을 그대로 재사용하는 편이 "또 하나의
빈 배선"을 만들지 않는 선택이다. `FORMAT_STRATEGY`는 "이 확장자를 시스템이 인지하는가"의
SSOT로만 재사용한다(신규 목록 발명 없음, technology_extractor.py와 동일 패턴).
"""

import io
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import tempfile

from backend.adapters.llm.ollama_semantic_judge import OLLAMA_URL, OllamaSemanticJudge
from backend.adapters.office_convert.libreoffice_bridge import (
    ConversionFailedError,
    ConversionTimeoutError,
    LibreOfficeNotFoundError,
    convert_to_pdf,
)
from backend.adapters.parsers.docx_adapter import DocxParserAdapter
from backend.adapters.parsers.hwp_adapter import HwpParserAdapter
from backend.adapters.parsers.pdf_adapter import PdfParserAdapter
from backend.adapters.parsers.pptx_adapter import PptxParserAdapter
from backend.adapters.parsers.router import FORMAT_STRATEGY
from backend.adapters.parsers.speech_to_text_adapter import (
    SUPPORTED_AUDIO_EXTENSIONS,
    SpeechToTextAdapter,
)
from backend.adapters.parsers.text_passthrough_adapter import TextPassthroughAdapter
from backend.adapters.parsers.xlsx_adapter import XlsxParserAdapter
from backend.adapters.persistence.document_store import DocumentStore
from backend.adapters.persistence.requirement_store import RequirementRecord, RequirementStore
from backend.application.ports.parser_port import ParserPort
from backend.application.services.requirement_extraction_service import extract_requirements_from_chunks
from backend.domain.chunking.heading_splitter import SemanticBoundarySplitter, SPCEngine

# plans/_plan/02_PHASE2_ORCHESTRATION_PREVIEW.md §8, W4 — DOCX/PPTX를 §8-2 PDF 통합
# 파이프라인에 편입시키는 확장자 집합. 변환 성공 시 이 포맷들은 PdfParserAdapter로
# 마크다운을 재추출하고 pdf_source도 함께 채운다(§8-6과 동일한 하위호환 원칙 —
# 변환 실패 시 기존 네이티브 어댑터로 조용히 폴백, 업로드 자체는 절대 막지 않는다).
_LIBREOFFICE_CONVERTIBLE_EXTS = {".docx", ".pptx"}

# 2026-07-22 (사용자 지시: "LLM 연동해서 청킹 퀄리티를 끌어올려야 한다"): 업로드마다 Ollama에
# 짧은 타임아웃으로 헬스체크 후 가용하면 SemanticBoundarySplitter(관계판단 포함), 불가하면
# 기존 HeadingBoundarySplitter(SPCEngine 기본값)로 조용히 성능저하 — 업로드 자체는 절대
# 막지 않는다(T99 AIOS 우아한 성능저하).
_OLLAMA_HEALTH_URL = OLLAMA_URL.rsplit("/api/", 1)[0] + "/api/tags"


def _build_chunking_splitter() -> SemanticBoundarySplitter | None:
    try:
        urllib.request.urlopen(_OLLAMA_HEALTH_URL, timeout=1.5)
    except (urllib.error.URLError, TimeoutError, OSError):
        return None  # Ollama 미기동 — SPCEngine 기본값(HeadingBoundarySplitter)으로 폴백
    return SemanticBoundarySplitter(judge=OllamaSemanticJudge())


# [2026-07-25 §D-777d8fd9] faster-whisper 모델은 지연 로딩한다 — 모듈 임포트 시점(서버
# 기동 시)에 즉시 WhisperModel을 로드하면 오디오를 한 번도 업로드하지 않는 세션에서도
# 매번 시작 지연 + 메모리 상주가 생긴다(T38 PAP 성능 적응형 판단). 실제 첫 오디오 업로드
# 시점에만 1회 빌드하고 이후 재사용한다.
_stt_engine_cache: dict[str, object] = {}


def _lazy_faster_whisper_engine(source_path: str):
    if "engine" not in _stt_engine_cache:
        from backend.adapters.parsers.faster_whisper_engine import build_faster_whisper_stt_engine

        _stt_engine_cache["engine"] = build_faster_whisper_stt_engine()
    return _stt_engine_cache["engine"](source_path)


# 실제 동작하는 ParserPort 구현체만 등록한다 — 새 포맷 어댑터가 완성되면 이 리스트에
# 추가하는 것이 유일한 확장 지점이다(§4 설계 명시).
_ADAPTERS: list[ParserPort] = [
    TextPassthroughAdapter(),
    DocxParserAdapter(),
    PptxParserAdapter(),  # 2026-07-22 추가 — python-pptx(기설치) 실동작 구현
    PdfParserAdapter(),  # 2026-07-22 추가 — pdfplumber(신규 설치) 실동작 구현
    XlsxParserAdapter(),  # 2026-07-22 추가 — openpyxl(기설치) 실동작 구현
    HwpParserAdapter(),  # 2026-07-22 추가 — pyhwp(신규 설치) 재사용, 사용자 결정: "olefile+커스텀 파싱"
    SpeechToTextAdapter(stt_engine=_lazy_faster_whisper_engine),  # 2026-07-25 추가 — faster-whisper(기설치) 지연연결
]


class UnsupportedUploadFormatError(ValueError):
    """FORMAT_STRATEGY에 없는(시스템이 아예 모르는) 확장자."""


class NotImplementedUploadFormatError(ValueError):
    """FORMAT_STRATEGY에는 있으나(§5-A 문서유형과 연결된 알려진 포맷) 실제 파서가 없는 확장자.

    거짓 성공 응답을 주지 않기 위해 UnsupportedUploadFormatError와 구분한다(T98 AIP —
    "이 포맷 자체를 모른다"와 "이 포맷은 알지만 아직 못 읽는다"는 사용자에게 다른 메시지가
    필요한 서로 다른 상황이다).
    """


@dataclass
class UploadResult:
    doc_id: str
    doc_filename: str
    chunk_count: int
    requirements_created: list[RequirementRecord] = field(default_factory=list)
    unclassified_chunk_count: int = 0
    # [§8 W4] 원본이 PDF였거나 LibreOffice로 PDF 변환에 성공한 경우에만 채워진다 — 호출부
    # (documents_api.upload_document)가 원본 확장자와 무관하게 이 바이트를 documents_raw/
    # {doc_id}.pdf로 저장해 페이지 이미지 렌더링(§8-4)이 동작하게 한다. 변환 실패/미해당
    # 포맷이면 None(§8-6 폴백 — page_number/bbox도 함께 None으로 남는다).
    pdf_bytes_for_page_render: bytes | None = None


def _pick_adapter(ext: str) -> ParserPort:
    ext = ext.lower()
    if ext not in FORMAT_STRATEGY:
        raise UnsupportedUploadFormatError(
            f"미지원 확장자: {ext} (허용: {sorted(FORMAT_STRATEGY)})"
        )
    for adapter in _ADAPTERS:
        if adapter.can_handle(ext):
            return adapter
    strategy = FORMAT_STRATEGY[ext]
    raise NotImplementedUploadFormatError(
        f"'{ext}'(전략: {strategy})는 아직 실제 파서가 구현되지 않았습니다 — "
        f"현재 업로드 가능한 확장자: {sorted(a for a in FORMAT_STRATEGY if any(x.can_handle(a) for x in _ADAPTERS))}"
    )


def process_uploaded_file(
    filename: str,
    content: bytes,
    actor: str,
    req_store: RequirementStore,
    doc_store: DocumentStore,
) -> UploadResult:
    """업로드된 파일 1건을 파싱→청킹→분류·채번까지 끝까지 처리한다.

    filename의 확장자로 어댑터를 고르고, 지원하지 않는/미구현 포맷이면 ValueError 계열
    예외(UnsupportedUploadFormatError/NotImplementedUploadFormatError)를 던진다 — 호출자
    (API 라우터)가 이를 4xx 응답으로 변환한다.

    [2026-07-23 정리] 이전에는 `frontend_export_path`가 주어지면 `RequirementStore.
    export_json()`으로 `frontend/data/requirements.json` 정적 스냅샷을 갱신했으나, 실측
    검토(§W-5) 결과 documents.html/requirements.html이 이미 2026-07-22에 실시간
    `GET /requirements?project_id=`로 전환되어 있어 그 정적 파일을 더 이상 아무도 읽지
    않는다(CRZ — 소비자 없는 write 경로 제거, 회귀 0 `pytest tests/` 확인)."""
    if not content:
        raise ValueError("빈 파일은 업로드할 수 없습니다")

    ext = Path(filename).suffix
    original_ext = ext

    # [§8 W4] DOCX/PPTX는 LibreOffice로 PDF 변환을 먼저 시도해, 성공하면 §8-2 설계 그대로
    # PDF 통합 파이프라인(PdfParserAdapter + pdf_bbox_adapter)에 편입시킨다 — 마크다운도
    # 변환된 PDF에서 재추출해 char_start/char_end가 bbox 조회와 항상 같은 텍스트 소스를
    # 쓰게 한다(서로 다른 추출엔진 간 오프셋 불일치 방지, DES 계열 실수 사전 차단). 변환
    # 실패(LibreOffice 미설치/타임아웃/손상 파일)는 **업로드를 막지 않고** 기존 네이티브
    # 어댑터(docx_adapter/pptx_adapter)로 조용히 폴백한다(T99 AIOS 우아한 성능저하 — Ollama
    # 헬스체크 폴백과 동일 패턴, CRZ).
    converted_pdf_bytes: bytes | None = None
    if ext.lower() in _LIBREOFFICE_CONVERTIBLE_EXTS:
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_dir_path = Path(tmp_dir)
                input_path = tmp_dir_path / f"upload{ext}"
                input_path.write_bytes(content)
                pdf_path = convert_to_pdf(input_path, tmp_dir_path)
                converted_pdf_bytes = pdf_path.read_bytes()
        except (LibreOfficeNotFoundError, ConversionTimeoutError, ConversionFailedError):
            converted_pdf_bytes = None  # 폴백 — 네이티브 어댑터로 계속 진행

    if converted_pdf_bytes is not None:
        ext = ".pdf"
        adapter = PdfParserAdapter()
        parse_source = converted_pdf_bytes
    else:
        adapter = _pick_adapter(original_ext)
        parse_source = content

    # [2026-07-25 §D-777d8fd9] SpeechToTextAdapter는 스트림이 아니라 metadata["source_path"]
    # (디스크 경로)를 요구한다(faster-whisper가 ffmpeg 디코딩에 실 경로가 필요, 어댑터
    # docstring §2 참고) — 오디오 확장자일 때만 임시 파일로 써서 전달, 전사 완료 후 정리.
    if original_ext.lower() in SUPPORTED_AUDIO_EXTENSIONS:
        with tempfile.TemporaryDirectory() as audio_tmp_dir:
            audio_path = Path(audio_tmp_dir) / f"upload{original_ext}"
            audio_path.write_bytes(parse_source)
            markdown = adapter.parse_to_markdown(
                io.BytesIO(parse_source), metadata={"filename": filename, "source_path": str(audio_path)}
            )
    else:
        markdown = adapter.parse_to_markdown(io.BytesIO(parse_source), metadata={"filename": filename})
    if not markdown.strip():
        raise ValueError("파싱 결과가 비어 있습니다 — 문서 내용을 확인하세요")

    doc_id = f"doc-{uuid.uuid4().hex[:12]}"
    doc_store.save(doc_id, markdown)

    semantic_splitter = _build_chunking_splitter()
    engine = SPCEngine(splitter=semantic_splitter) if semantic_splitter else SPCEngine()
    chunks = engine.process_document(markdown, context_label=filename, doc_id=doc_id)

    # plans/_plan/02_PHASE2_ORCHESTRATION_PREVIEW.md §8 — PDF(원본이거나 위에서 변환됨)만
    # 원본 바이트를 그대로 넘겨 pdf_bbox_adapter.locate()가 page_number/bbox를 채울 수 있게
    # 한다(다른 포맷·변환실패는 None 유지, §8-3 하위호환).
    pdf_source = parse_source if ext.lower() == ".pdf" else None
    records = extract_requirements_from_chunks(
        chunks, req_store, doc_format=ext, pdf_source=pdf_source
    )

    child_chunk_count = sum(1 for c in chunks if c.parent_id is not None)
    unclassified = child_chunk_count - len(records)

    return UploadResult(
        doc_id=doc_id,
        doc_filename=filename,
        chunk_count=child_chunk_count,
        requirements_created=records,
        unclassified_chunk_count=unclassified,
        pdf_bytes_for_page_render=parse_source if ext.lower() == ".pdf" else None,
    )
