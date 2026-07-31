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
    process_uploaded_file,
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


def test_process_uploaded_file_rejects_empty_content_directly(tmp_path):
    """[커버리지 보완] `process_uploaded_file()` 자신의 빈 콘텐츠 방어 로직 —
    `documents_api.upload_document()`가 이미 동일 검사를 먼저 수행해 API 경로로는 이
    분기에 도달하지 않는다(실측 확인). 이 서비스 함수를 API를 거치지 않고 직접 호출하는
    경우(단위테스트·향후 다른 호출부)를 위한 방어 로직이 여전히 살아있는지 직접 검증한다."""
    from backend.adapters.persistence.document_store import DocumentStore
    from backend.adapters.persistence.requirement_store import RequirementStore

    req_store = RequirementStore(tmp_path / "requirements_store.json")
    doc_store = DocumentStore(tmp_path / "documents")
    with pytest.raises(ValueError, match="빈 파일"):
        process_uploaded_file(
            filename="empty.txt", content=b"", actor="tester", req_store=req_store, doc_store=doc_store,
        )


def test_build_chunking_splitter_falls_back_to_none_when_ollama_unreachable(monkeypatch):
    """[커버리지 보완] Ollama 헬스체크(urlopen)가 실패하면(URLError/TimeoutError/OSError)
    None을 반환해 SPCEngine이 기본값(HeadingBoundarySplitter)으로 조용히 성능저하돼야
    한다(T99 AIOS) — 실제 Ollama 기동 여부와 무관하게 이 폴백 분기를 직접 검증한다."""
    import backend.application.services.document_upload_service as svc

    def _raise_url_error(*args, **kwargs):
        raise svc.urllib.error.URLError("테스트: Ollama 미기동 시뮬레이션")

    monkeypatch.setattr(svc.urllib.request, "urlopen", _raise_url_error)
    assert svc._build_chunking_splitter() is None
