"""PDF 좌표(bbox)·페이지 위치 추적 어댑터(pdf_bbox_adapter.py) 테스트.

reportlab로 합성 PDF(2페이지, 알려진 위치의 텍스트)를 만들어 `extract_text()`가 페이지
구분자를 포함한 문자열을 만드는지, `locate()`가 실제로 그 텍스트가 있는 페이지·bbox를
정확히 찾는지, 매칭 실패 시 `(None, None)`을 정직하게 반환하는지 검증한다(placeholder
반환 금지, T98 AIP). tests/test_pdf_adapter.py와 동일하게 reportlab 합성 PDF를 쓴다(CRZ).
"""

import io

from reportlab.pdfgen import canvas

from backend.adapters.parsers import pdf_bbox_adapter


def _build_two_page_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))  # letter
    c.drawString(100, 700, "Hello PDF World")
    c.showPage()
    c.drawString(100, 650, "Second page marker text")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def _build_empty_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.save()
    buf.seek(0)
    return buf.read()


def test_extract_text_contains_page_headers_and_text():
    pdf_bytes = _build_two_page_pdf()
    text = pdf_bbox_adapter.extract_text(pdf_bytes)

    assert "## Page 1" in text
    assert "## Page 2" in text
    assert "Hello PDF World" in text
    assert "Second page marker text" in text
    # 페이지 순서 보존 확인 — Page 1 텍스트가 Page 2 텍스트보다 앞서 나와야 한다.
    assert text.index("Hello PDF World") < text.index("Second page marker text")


def test_locate_finds_correct_page_and_bbox_for_page1_text():
    pdf_bytes = _build_two_page_pdf()
    text = pdf_bbox_adapter.extract_text(pdf_bytes)

    start = text.index("Hello PDF World")
    end = start + len("Hello PDF World")

    page_number, bbox = pdf_bbox_adapter.locate(pdf_bytes, start, end)

    assert page_number == 1
    assert bbox is not None
    assert len(bbox) == 4
    x0, y0, x1, y1 = bbox
    assert x0 < x1
    assert y0 < y1


def test_locate_finds_correct_page_for_page2_text():
    pdf_bytes = _build_two_page_pdf()
    text = pdf_bbox_adapter.extract_text(pdf_bytes)

    start = text.index("Second page marker text")
    end = start + len("Second page marker text")

    page_number, bbox = pdf_bbox_adapter.locate(pdf_bytes, start, end)

    assert page_number == 2
    assert bbox is not None


def test_locate_returns_none_none_when_offset_out_of_range():
    pdf_bytes = _build_two_page_pdf()
    text = pdf_bbox_adapter.extract_text(pdf_bytes)

    # 문서 전체 길이보다 훨씬 뒤쪽의 오프셋 — 어느 span에도 걸리지 않아야 한다.
    far_start = len(text) + 1000
    far_end = far_start + 10

    page_number, bbox = pdf_bbox_adapter.locate(pdf_bytes, far_start, far_end)

    assert page_number is None
    assert bbox is None


def test_locate_returns_none_none_for_none_offsets():
    pdf_bytes = _build_two_page_pdf()
    assert pdf_bbox_adapter.locate(pdf_bytes, None, None) == (None, None)
    assert pdf_bbox_adapter.locate(pdf_bytes, 5, None) == (None, None)


def test_locate_returns_none_none_for_empty_pdf():
    pdf_bytes = _build_empty_pdf()
    page_number, bbox = pdf_bbox_adapter.locate(pdf_bytes, 0, 5)

    assert page_number is None
    assert bbox is None


def test_extract_text_empty_pdf_returns_empty_string():
    pdf_bytes = _build_empty_pdf()
    text = pdf_bbox_adapter.extract_text(pdf_bytes)

    assert text == ""
