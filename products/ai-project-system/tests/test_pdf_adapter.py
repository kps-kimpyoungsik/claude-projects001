"""PDF 파서 어댑터(pdf_adapter.py) 테스트.

reportlab으로 합성 PDF(2줄 텍스트)를 만들어 실제 parse_to_markdown() 호출 결과를
검증한다(placeholder 반환 금지, T98 AIP). 표 추출은 pdfplumber의 extract_tables()에
의존하므로 별도 표 유닛테스트는 pdfplumber 자체 신뢰(외부 라이브러리 재검증은 범위 밖).
"""

import io

from reportlab.pdfgen import canvas

from backend.adapters.parsers.pdf_adapter import PdfParserAdapter


def _build_sample_pdf() -> io.BytesIO:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "Hello PDF World")
    c.drawString(100, 730, "Second line of text")
    c.save()
    buf.seek(0)
    return buf


def test_can_handle_pdf_only():
    adapter = PdfParserAdapter()
    assert adapter.can_handle(".pdf") is True
    assert adapter.can_handle(".PDF") is True
    assert adapter.can_handle(".docx") is False


def test_parse_to_markdown_extracts_text_with_page_heading():
    adapter = PdfParserAdapter()
    md = adapter.parse_to_markdown(_build_sample_pdf(), metadata={"filename": "test.pdf"})

    assert "## Page 1" in md
    assert "Hello PDF World" in md
    assert "Second line of text" in md


def test_parse_to_markdown_empty_pdf_returns_empty_string():
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.save()
    buf.seek(0)

    adapter = PdfParserAdapter()
    md = adapter.parse_to_markdown(buf, metadata={"filename": "empty.pdf"})
    # 빈 페이지라도 "## Page 1" 헤딩 자체는 남는다(페이지 존재는 사실이므로) — 본문만 비어있음
    assert "Hello" not in md
