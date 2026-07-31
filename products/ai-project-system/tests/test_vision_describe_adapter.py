"""이미지(vision) 업로드 어댑터 단위 테스트 — D-011db847 후속.

실제 vision 엔진(Ollama moondream)은 호출하지 않는다 — vision_engine 콜백을 mock으로
주입해 "설명문 렌더링 + 콜백 주입 구조"만 검증한다(tests/test_speech_to_text_adapter.py와
동일 패턴, CRZ). 실제 엔진 e2e는 tests/test_documents_upload_api.py의
test_upload_png_image_describes_via_ollama_vision이 담당한다.
"""

import pytest

from backend.adapters.parsers.format_dispatch import FORMAT_STRATEGY
from backend.adapters.parsers.vision_describe_adapter import (
    SUPPORTED_IMAGE_EXTENSIONS,
    VisionDescribeAdapter,
)


def test_router_maps_image_extensions_to_vision_describe_strategy():
    for ext in SUPPORTED_IMAGE_EXTENSIONS:
        assert FORMAT_STRATEGY[ext] == "vision_describe"


def _fake_vision_engine(source_path: str) -> str:
    assert source_path == "uploads/photo.png"
    return "빨간색 사각형 이미지."


def test_can_handle_image_extensions():
    adapter = VisionDescribeAdapter()
    for ext in SUPPORTED_IMAGE_EXTENSIONS:
        assert adapter.can_handle(ext)
        assert adapter.can_handle(ext.upper())  # 대소문자 무관
    assert not adapter.can_handle(".docx")


def test_no_engine_injected_raises_not_implemented():
    adapter = VisionDescribeAdapter()  # vision_engine 미주입
    with pytest.raises(NotImplementedError):
        adapter.parse_to_markdown(file_stream=None, metadata={"source_path": "uploads/photo.png"})


def test_missing_source_path_raises_value_error():
    adapter = VisionDescribeAdapter(vision_engine=_fake_vision_engine)
    with pytest.raises(ValueError):
        adapter.parse_to_markdown(file_stream=None, metadata={})


def test_parse_to_markdown_renders_description():
    adapter = VisionDescribeAdapter(vision_engine=_fake_vision_engine)
    markdown = adapter.parse_to_markdown(file_stream=None, metadata={"source_path": "uploads/photo.png"})
    assert "## 이미지 설명" in markdown
    assert "빨간색 사각형 이미지." in markdown


def test_parse_to_markdown_empty_description_returns_empty_string():
    adapter = VisionDescribeAdapter(vision_engine=lambda path: "")
    markdown = adapter.parse_to_markdown(file_stream=None, metadata={"source_path": "uploads/photo.png"})
    assert markdown == ""
