"""[Phase 2 §8-4, W4] libreoffice_bridge.py 실통합 테스트.

mock 없이 **실제 LibreOffice headless 변환**을 호출한다(§0-5 Pre-Q "실측 우선" 원칙 —
subprocess 래퍼를 목업으로만 검증하면 실제 hang·경로 문제를 못 잡는다). 이 프로젝트
개발환경에 LibreOffice가 없으면(CI 등) `LibreOfficeNotFoundError`로 스킵한다 — 없다고
거짓으로 PASS 처리하지 않는다(T98 AIP).
"""

import io

import pytest
from docx import Document

from backend.adapters.office_convert.libreoffice_bridge import (
    ConversionFailedError,
    LibreOfficeNotFoundError,
    convert_to_pdf,
)


def _build_sample_docx(path):
    doc = Document()
    doc.add_paragraph("Security requirement: encryption must be applied to all traffic.")
    doc.save(str(path))


@pytest.fixture
def skip_if_no_libreoffice():
    try:
        from backend.adapters.office_convert.libreoffice_bridge import _soffice_path
        _soffice_path()
    except LibreOfficeNotFoundError:
        pytest.skip("LibreOffice 미설치 환경 — 실통합 테스트 스킵(§0-5, 거짓 PASS 금지)")


def test_convert_docx_to_pdf_real(tmp_path, skip_if_no_libreoffice):
    docx_path = tmp_path / "sample.docx"
    _build_sample_docx(docx_path)

    out_dir = tmp_path / "converted"
    pdf_path = convert_to_pdf(docx_path, out_dir, timeout=120)

    assert pdf_path.exists()
    assert pdf_path.suffix == ".pdf"
    # PyMuPDF로 실제 유효한 PDF인지 + 텍스트가 살아있는지 확인(빈 파일/손상 파일이면 실패)
    import pymupdf as fitz
    with fitz.open(str(pdf_path)) as pdf:
        assert pdf.page_count >= 1
        text = pdf[0].get_text()
        assert "encryption" in text.lower()


def test_convert_missing_input_raises(tmp_path, skip_if_no_libreoffice):
    missing = tmp_path / "does_not_exist.docx"
    out_dir = tmp_path / "converted"
    with pytest.raises(ConversionFailedError):
        convert_to_pdf(missing, out_dir, timeout=30)


def test_soffice_not_found_raises_when_env_override_invalid(monkeypatch, tmp_path):
    monkeypatch.setenv("LIBREOFFICE_SOFFICE_PATH", str(tmp_path / "nonexistent_soffice.exe"))
    with pytest.raises(LibreOfficeNotFoundError):
        convert_to_pdf(tmp_path / "x.docx", tmp_path / "out")
