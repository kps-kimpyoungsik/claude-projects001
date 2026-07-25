"""HWP 파서 어댑터(hwp_adapter.py) 테스트.

pyhwp가 실제로 유효성 검증을 어떻게 하는지는 무작위 바이트로 실측 가능(부정 경로).
**정직 고지**: 실제 유효한 .hwp 파일도, 이를 만들 라이브러리도 이 환경에 없어
긍정 경로(올바른 텍스트 추출)는 이 테스트로 검증되지 않는다 — hwp_adapter.py
docstring에 동일하게 명시(T98 AIP, 추정 검증 금지).
"""

import io

import pytest

from backend.adapters.parsers.hwp_adapter import HwpParserAdapter, HwpParsingError


def test_can_handle_hwp_only():
    adapter = HwpParserAdapter()
    assert adapter.can_handle(".hwp") is True
    assert adapter.can_handle(".HWP") is True
    assert adapter.can_handle(".docx") is False


def test_invalid_ole_bytes_raise_hwp_parsing_error():
    """무작위 바이트(OLE2 컴파운드 파일이 아님) → 실제 InvalidHwp5FileError 발생을
    HwpParsingError로 변환해 호출자(업로드 API)가 4xx로 응답하도록 한다."""
    adapter = HwpParserAdapter()
    garbage = io.BytesIO(b"this is not a valid hwp file, just plain garbage bytes")
    with pytest.raises(HwpParsingError):
        adapter.parse_to_markdown(garbage, metadata={"filename": "bad.hwp"})
