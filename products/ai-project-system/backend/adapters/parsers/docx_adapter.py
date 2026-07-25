"""[Phase 2] DOCX -> Markdown 어댑터 (실제 동작 구현, 외부 의존성 0).

사용자 제안 코드는 `return "## Extracted Content from DOCX\n..."`처럼 실제 파싱 없이
placeholder 문자열만 반환했다 — 이를 "동작하는 것"으로 보고할 수 없어(T98 AIP 정직성),
Python 표준 라이브러리(zipfile + xml.etree)만으로 실제 텍스트/표 추출을 구현했다.
Unstructured.io 등 외부 라이브러리는 이 환경에 설치되어 있지 않아(미확인) 사용하지 않는다.

.docx는 zip 컨테이너이며 본문은 word/document.xml의 OOXML이다 — python-docx 등
외부 패키지 없이도 표준 스키마(w:p/w:r/w:t, w:tbl/w:tr/w:tc)만으로 단락·표를 추출할 수 있다.
"""

import zipfile
from typing import Any, BinaryIO
from xml.etree import ElementTree as ET

from backend.application.ports.parser_port import ParserPort

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DocxParserAdapter(ParserPort):
    def can_handle(self, file_extension: str) -> bool:
        return file_extension.lower() in (".docx",)
        # .doc(구버전 바이너리 포맷)는 OOXML이 아니라 이 방식으로 파싱 불가 — can_handle에서 제외

    def parse_to_markdown(self, file_stream: BinaryIO, metadata: dict[str, Any]) -> str:
        with zipfile.ZipFile(file_stream) as z:
            xml_bytes = z.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
        body = root.find(f"{W_NS}body")
        if body is None:
            return ""

        lines: list[str] = []
        for element in body:
            tag = element.tag
            if tag == f"{W_NS}p":
                text = self._paragraph_text(element)
                if text:
                    lines.append(text)
            elif tag == f"{W_NS}tbl":
                lines.append(self._table_to_markdown(element))
        return "\n\n".join(lines)

    def _paragraph_text(self, p_element) -> str:
        runs = p_element.findall(f".//{W_NS}t")
        return "".join(r.text or "" for r in runs)

    def _table_to_markdown(self, tbl_element) -> str:
        rows = []
        for tr in tbl_element.findall(f"{W_NS}tr"):
            cells = [self._paragraph_text(tc) for tc in tr.findall(f"{W_NS}tc")]
            rows.append(cells)
        if not rows:
            return ""
        header = "| " + " | ".join(rows[0]) + " |"
        sep = "| " + " | ".join(["---"] * len(rows[0])) + " |"
        body_rows = ["| " + " | ".join(r) + " |" for r in rows[1:]]
        return "\n".join([header, sep, *body_rows])
