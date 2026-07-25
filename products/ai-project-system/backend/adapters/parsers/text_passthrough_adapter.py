"""[문서 업로드 파이프라인] .txt/.md 텍스트 원문 → 정규화 마크다운 어댑터.

`router.py`의 `FORMAT_STRATEGY["text_passthrough"]`가 가리키는 실제 구현체다.
`docx_adapter.DocxParserAdapter`와 동일한 `ParserPort` 계약을 따른다(CRZ — 새 인터페이스
발명 없음). 이미 마크다운/평문 텍스트이므로 "정규화"는 인코딩 디코딩뿐이다.

인코딩: UTF-8을 우선 시도하고, 실패하면 CP949(EUC-KR 상위호환, Windows 한글 텍스트의
사실상 표준)로 재시도한다. 두 인코딩 모두 실패하면 예외를 그대로 전파한다 — 깨진 문자로
조용히 채우지 않는다(추정 디코딩 금지, T98 AIP).
"""

from typing import Any, BinaryIO

from backend.application.ports.parser_port import ParserPort

SUPPORTED_EXTENSIONS = (".txt", ".md")


class TextPassthroughAdapter(ParserPort):
    def can_handle(self, file_extension: str) -> bool:
        return file_extension.lower() in SUPPORTED_EXTENSIONS

    def parse_to_markdown(self, file_stream: BinaryIO, metadata: dict[str, Any]) -> str:
        raw = file_stream.read()
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("cp949")
