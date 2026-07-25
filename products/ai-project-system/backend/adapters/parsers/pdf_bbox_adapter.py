"""[Phase 2 §8 W1] PDF 좌표(bbox)·페이지 위치 추적 어댑터 (PyMuPDF 기반).

`plans/_plan/02_PHASE2_ORCHESTRATION_PREVIEW.md` §8-2·§8-3·§8-4·§8-7(W1 행) 설계를
그대로 구현한다.

**아키텍처 결정(§8-2 그대로)**: 이 프로젝트에 이미 설치된 PyMuPDF(``pymupdf``, 텍스트+bbox
추출과 페이지 래스터화를 별도 시스템 의존성 없이 단일 라이브러리로 처리 가능)를 좌표 파이프라인
전용으로 쓴다. **기존 `pdf_adapter.py`(pdfplumber 기반)는 절대 수정하지 않는다** — 그 모듈의
`ParserPort` 계약(`parse_to_markdown`)은 그대로 유지되고, 이 모듈은 그 위에 얹히는 **상위
확장판**(bbox·페이지 조회 전용 순수 함수 모음, `ParserPort` 구현 아님)이다.

**"동일 텍스트" 정직성 한계(T98 AIP)**: `extract_text()`는 `PdfParserAdapter.
parse_to_markdown()`과 같은 구조(페이지 구분자 ``## Page N``, 표 서브헤딩
``### Table N (Page M)``)를 재현하지만, 실제 문자 단위 추출 엔진이 다르다(pdfplumber vs
PyMuPDF) — 텍스트 레이어가 정상인 일반 문서는 사실상 동일하게 나오지만, **표가 있는 페이지나
비표준 공백 처리가 있는 PDF는 문자 단위로 100% 동일함을 보장하지 않는다**(과장 금지). 이 모듈
내부에서는 `extract_text()`와 `locate()`가 항상 같은 텍스트 재구성 함수(`_build_index`)를
공유하므로 **이 모듈 자기 자신과는 항상 정합**하다 — 다만 `requirement_extraction_service.py`가
실제로 참조하는 `char_start`/`char_end`는 `PdfParserAdapter`(pdfplumber)가 만든 마크다운 기준
오프셋이라는 점은 구현 완료 보고에 한계로 명시한다.

`ParserPort`를 구현하지 않는다(설계 §8-4 그대로 "보조 유틸리티 모듈") — 순수 함수형:
- `extract_text(pdf_source)` — 페이지 순서대로 이어붙인 문자열.
- `locate(pdf_path, char_start, char_end)` — 그 문자열 기준 오프셋이 속한 페이지 번호
  (1-based)와 bbox(`[x0, y0, x1, y1]`, PDF 포인트 좌표)를 반환. 매칭 실패 시 `(None, None)`
  (추정 금지, 정직 반환).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO, Union

try:
    # PyMuPDF >= 1.24 부터 공식 모듈명이 `pymupdf`다(`fitz`는 하위호환 별칭으로 계속 제공됨).
    # 이 개발환경 실측(2026-07-25): `import pymupdf` 자체가 `fitz`와 동일 객체를 제공하므로
    # `import pymupdf as fitz`로 기존 PyMuPDF 예제 코드·문서 관용구를 그대로 쓸 수 있다.
    import pymupdf as fitz
except ImportError:  # pragma: no cover - 구버전 PyMuPDF만 설치된 환경 호환
    import fitz  # type: ignore[no-redef]

PdfSource = Union[str, Path, bytes, bytearray, BinaryIO]

# (start, end, page_number(1-based), bbox[x0,y0,x1,y1]) — _build_index()가 만드는 색인 엔트리.
_SpanEntry = tuple[int, int, int, list[float]]

# 단일 문서를 여러 요구사항 레코드가 반복 조회하는 호출 패턴(문서 1개당 locate() N회) 대비
# 소규모 캐시. 무한 누적 방지를 위해 상한(4개 문서)을 넘으면 가장 오래된 것부터 비운다.
_CACHE_MAXSIZE = 4
_index_cache: dict[str, tuple[str, list[_SpanEntry]]] = {}
_cache_order: list[str] = []


def _open(source: PdfSource):
    if isinstance(source, (bytes, bytearray)):
        return fitz.open(stream=bytes(source), filetype="pdf")
    if hasattr(source, "read") and not isinstance(source, (str, Path)):
        return fitz.open(stream=source.read(), filetype="pdf")
    return fitz.open(str(source))


def _cache_key(source: PdfSource) -> str:
    if isinstance(source, (bytes, bytearray)):
        # 파일 경로가 없는(업로드 시점 in-memory) 호출 — 바이트 해시로 동일 문서 여부 판별.
        return "bytes:" + hashlib.sha1(bytes(source)).hexdigest()
    return "path:" + str(source)


def _table_to_markdown(rows: list[list]) -> list[str]:
    """`pdf_adapter.py`의 `PdfParserAdapter._table_to_markdown()`과 동일한 서식.

    두 모듈이 서로 import하지 않는 이유: `pdf_adapter.py`는 절대 수정하지 않는다는 작업
    규칙이 있고, 이 모듈도 그 파일을 건드리지 않으면서 동일 서식만 재현해야 하므로 서식
    로직 자체를 여기 복제한다(로직은 5줄 수준의 순수 포맷팅 — 별도 공유 모듈로 뽑는 것은
    이번 W1 범위 밖의 리팩토링, over-engineering 회피).
    """
    clean_rows = [[(cell or "").strip() for cell in row] for row in rows if row]
    if not clean_rows:
        return []
    out = [
        "| " + " | ".join(clean_rows[0]) + " |",
        "| " + " | ".join("---" for _ in clean_rows[0]) + " |",
    ]
    for row in clean_rows[1:]:
        out.append("| " + " | ".join(row) + " |")
    return out


def _page_text_and_spans(page) -> tuple[str, list[tuple[int, int, list[float]]]]:
    """`page.get_text("dict")`의 span 단위로 페이지 텍스트를 재구성하며, 각 span이 이
    페이지 텍스트 안에서 차지하는 `[start, end)` 오프셋과 bbox를 함께 기록한다.

    `get_text("text")`를 따로 부르지 않는 이유: `extract_text()`와 `locate()`가 서로 다른
    텍스트 재구성 로직을 쓰면 그 사이 공백/개행 처리 차이만으로 오프셋이 어긋난다 — 이
    함수 하나를 두 진입점이 공유해야 최소한 이 모듈 내부 정합이 보장된다.
    """
    parts: list[str] = []
    spans: list[tuple[int, int, list[float]]] = []
    cursor = 0
    raw = page.get_text("dict")
    for block in raw.get("blocks", []):
        if block.get("type", 0) != 0:
            continue  # 이미지 블록(type=1)은 텍스트 좌표 대상이 아니다
        for line in block.get("lines", []):
            line_has_text = False
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text:
                    continue
                start = cursor
                parts.append(text)
                cursor += len(text)
                bbox = list(span.get("bbox", [0.0, 0.0, 0.0, 0.0]))
                spans.append((start, cursor, bbox))
                line_has_text = True
            if line_has_text:
                parts.append("\n")
                cursor += 1
        parts.append("\n")
        cursor += 1
    return "".join(parts), spans


def _extract_tables(page) -> list[tuple[list[list], list[float] | None]]:
    """PyMuPDF 표 탐지(`page.find_tables()`). 버전/문서에 따라 API 부재·탐지 실패가 있을 수
    있어 실패해도 조용히 빈 목록으로 폴백한다 — 표 미탐지가 페이지 텍스트+bbox 추출 전체를
    막아서는 안 된다(T99 AIOS 우아한 성능저하)."""
    try:
        finder = page.find_tables()
    except Exception:
        return []
    tables: list[tuple[list[list], list[float] | None]] = []
    for table in getattr(finder, "tables", []):
        try:
            rows = table.extract()
        except Exception:
            continue
        bbox = list(table.bbox) if getattr(table, "bbox", None) else None
        tables.append((rows, bbox))
    return tables


def _build_index(source: PdfSource) -> tuple[str, list[_SpanEntry]]:
    """(전체 텍스트, 색인) 튜플을 만든다 — `extract_text()`·`locate()` 둘 다 이 함수 하나만
    쓴다(CRZ, 텍스트 재구성 로직 중복 정의 금지).

    표 영역은 span 단위 bbox가 없으므로(마크다운 표로 평탄화된 텍스트) `page.find_tables()`가
    돌려준 표 전체 bbox를 그 구간 전부에 부여한다 — 셀 단위 정밀도는 없다(정직하게 한계로
    남김, §8-3 설계는 span 단위를 명시했으나 표는 span 개념이 없는 구조라 표 단위가 현실적
    최선).
    """
    doc = _open(source)
    try:
        parts: list[str] = []
        entries: list[_SpanEntry] = []
        cursor = 0

        def emit(text: str) -> None:
            nonlocal cursor
            parts.append(text)
            cursor += len(text)

        for page_idx, page in enumerate(doc, start=1):
            emit(f"## Page {page_idx}")
            emit("\n")

            page_text, spans = _page_text_and_spans(page)
            trimmed = page_text.rstrip("\n")
            if trimmed:
                start_offset = cursor
                emit(trimmed)
                trimmed_len = len(trimmed)
                for s, e, bbox in spans:
                    if s >= trimmed_len:
                        continue
                    e = min(e, trimmed_len)
                    if e <= s:
                        continue
                    entries.append((start_offset + s, start_offset + e, page_idx, bbox))
                emit("\n")
            emit("\n")

            for t_idx, (rows, bbox) in enumerate(_extract_tables(page), start=1):
                table_lines = _table_to_markdown(rows)
                if not table_lines:
                    continue
                table_start = cursor
                emit(f"### Table {t_idx} (Page {page_idx})")
                emit("\n")
                for line in table_lines:
                    emit(line)
                    emit("\n")
                table_end = cursor
                if bbox:
                    entries.append((table_start, table_end, page_idx, bbox))
                emit("\n")

        full_text = "".join(parts)
        full_text = (full_text.strip() + "\n") if full_text.strip() else ""
        return full_text, entries
    finally:
        doc.close()


def _cached_index(source: PdfSource) -> tuple[str, list[_SpanEntry]]:
    key = _cache_key(source)
    if key in _index_cache:
        return _index_cache[key]
    result = _build_index(source)
    _index_cache[key] = result
    _cache_order.append(key)
    if len(_cache_order) > _CACHE_MAXSIZE:
        oldest = _cache_order.pop(0)
        _index_cache.pop(oldest, None)
    return result


def extract_text(pdf_source: PdfSource) -> str:
    """페이지 순서대로 이어붙인 문자열 — `PdfParserAdapter.parse_to_markdown()`과 같은
    구조(페이지 구분자·표 서브헤딩)를 재현한다. 모듈 docstring의 정직성 한계 참조."""
    full_text, _ = _cached_index(pdf_source)
    return full_text


def locate(
    pdf_path: PdfSource, char_start: int | None, char_end: int | None
) -> tuple[int | None, list[float] | None]:
    """`extract_text(pdf_path)` 기준 `[char_start, char_end)` 오프셋을 포함하는 최소 span
    (들)의 페이지 번호(1-based)와 bbox(합집합)를 반환한다.

    매칭되는 span이 하나도 없으면(오프셋이 범위 밖이거나 페이지 사이 구분자/빈 줄 구간에만
    걸림) `(None, None)`을 정직하게 반환한다 — 추정 금지.
    """
    if char_start is None or char_end is None:
        return (None, None)
    if char_end <= char_start:
        return (None, None)

    try:
        _, entries = _cached_index(pdf_path)
    except Exception:
        # 손상된/열 수 없는 PDF — 조용히 실패시키지 않되(로그는 호출자 책임), 정직하게
        # 매칭 실패로 반환한다.
        return (None, None)

    matches = [e for e in entries if e[0] < char_end and e[1] > char_start]
    if not matches:
        return (None, None)

    pages = {m[2] for m in matches}
    if len(pages) > 1:
        # 여러 페이지에 걸친 범위 — 페이지 경계를 넘는 bbox 합집합은 의미가 없으므로
        # 가장 앞 페이지만 채택한다(정직한 근사, 추정 확대 금지).
        target_page = min(pages)
        matches = [m for m in matches if m[2] == target_page]
    else:
        target_page = matches[0][2]

    x0 = min(m[3][0] for m in matches)
    y0 = min(m[3][1] for m in matches)
    x1 = max(m[3][2] for m in matches)
    y1 = max(m[3][3] for m in matches)
    return target_page, [x0, y0, x1, y1]
