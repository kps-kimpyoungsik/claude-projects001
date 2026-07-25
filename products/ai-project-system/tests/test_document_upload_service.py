"""document_upload_service._pick_adapter 확장자 인식 테스트.

2026-07-22: PptxParserAdapter/PdfParserAdapter/XlsxParserAdapter/HwpParserAdapter를
_ADAPTERS에 신규 등록한 것을 회귀 없이 검증한다(등록 누락 시 NotImplementedUploadFormatError로
조용히 실패하는 것을 방지 — 등록 리스트 자체를 테스트로 고정, CRZ 재발명 없이 기존
_pick_adapter 재사용). FORMAT_STRATEGY에는 있으나 실제 파서가 없는 확장자가 현재
전무하므로(모든 등록 포맷 구현 완료), NotImplementedUploadFormatError 경로는
FORMAT_STRATEGY에 등록되지 않은 미지 확장자(UnsupportedUploadFormatError)와는
별개로 여전히 존재하는 코드 경로임을 회귀 방지 차원에서 직접 남겨둔다(가상의
strategy 문자열로 재현).
"""

import pytest

from backend.application.services.document_upload_service import (
    NotImplementedUploadFormatError,
    UnsupportedUploadFormatError,
    _pick_adapter,
)


@pytest.mark.parametrize("ext", [".txt", ".md", ".docx", ".pptx", ".pdf", ".xlsx", ".hwp"])
def test_pick_adapter_resolves_supported_formats(ext):
    adapter = _pick_adapter(ext)
    assert adapter.can_handle(ext) is True


def test_pick_adapter_raises_not_implemented_for_registered_but_unadapted_format(monkeypatch):
    """FORMAT_STRATEGY에는 있으나 _ADAPTERS 어댑터가 없는 상황을 가상 확장자로 재현한다
    (실제 등록 포맷은 이제 전부 구현되어 있어, 이 코드 경로 자체가 죽지 않았음을 별도로 고정)."""
    import backend.application.services.document_upload_service as svc

    monkeypatch.setitem(svc.FORMAT_STRATEGY, ".zzz", "unstructured_parse")
    with pytest.raises(NotImplementedUploadFormatError):
        _pick_adapter(".zzz")


def test_pick_adapter_raises_for_unknown_extension():
    with pytest.raises(UnsupportedUploadFormatError):
        _pick_adapter(".xyz")
