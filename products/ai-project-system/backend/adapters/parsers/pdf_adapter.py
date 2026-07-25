"""[Phase 2 후속] PDF -> Markdown 어댑터 (실제 동작 구현, pdfplumber 사용).

`router.py`의 FORMAT_STRATEGY[".pdf"] = "unstructured_parse"(표는 마크다운 표로 변환)
설계를 실제 구현한다. PDF는 docx/pptx(OOXML zip 컨테이너)와 달리 표준 스키마가 없어
stdlib만으로 재구현하는 것이 비현실적 — `pdfplumber`를 신규 설치해 사용한다(2026-07-22,
`pip install pdfplumber` 실행 근거는 이 파일의 git/작업 이력 참조, T98 AIP: 없는 라이브러리를
있다고 가정하지 않고 실제 설치 확인 후 사용).

한계(정직 기록): 스캔본 이미지 PDF(텍스트 레이어 없음)는 추출 결과가 비어 있을 수 있다
(OCR 미구현 — vision_describe 전략과는 별개 축, 이 어댑터 범위 밖).

[2026-07-22 청킹 방법론 재검토 반영] 외부 최신 사례(RAG 청킹 2026 모범사례 — 표는 프로즈와
섞지 않고 별도 청크로 분리) 조사 결과, 페이지 본문 뒤에 표를 인라인으로 붙이던 기존 구현은
표가 있는 페이지에서 산문+표 혼합 청크를 만드는 문제가 있었다. 표마다 "### Table N (Page M)"
서브헤딩을 붙여 페이지 본문과 별도 청크로 분리한다(pptx_adapter.py와 동일 원칙, CRZ).
"""

from typing import Any, BinaryIO

import pdfplumber

from backend.application.ports.parser_port import ParserPort


class PdfParserAdapter(ParserPort):
    def can_handle(self, file_extension: str) -> bool:
        return file_extension.lower() in (".pdf",)

    def parse_to_markdown(self, file_stream: BinaryIO, metadata: dict[str, Any]) -> str:
        lines: list[str] = []
        with pdfplumber.open(file_stream) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                lines.append(f"## Page {idx}")
                text = page.extract_text() or ""
                if text.strip():
                    lines.append(text.strip())
                lines.append("")
                # 표는 페이지 본문과 섞지 않고 서브헤딩(###)으로 별도 청크 경계를 만든다
                # (2026-07-22 청킹 방법론 재검토 — docstring 참조).
                for table_idx, table in enumerate(page.extract_tables() or [], start=1):
                    table_lines = self._table_to_markdown(table)
                    if not table_lines:
                        continue
                    lines.append(f"### Table {table_idx} (Page {idx})")
                    lines.extend(table_lines)
                    lines.append("")
        return "\n".join(lines).strip() + "\n" if lines else ""

    def _table_to_markdown(self, table: list[list]) -> list[str]:
        rows = [[(cell or "").strip() for cell in row] for row in table if row]
        if not rows:
            return []
        out = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join("---" for _ in rows[0]) + " |"]
        for row in rows[1:]:
            out.append("| " + " | ".join(row) + " |")
        return out
