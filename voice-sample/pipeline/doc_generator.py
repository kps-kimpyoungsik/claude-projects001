"""
doc_generator.py
LLM 요약 결과 → 다형식 문서 생성 (DOCX / PDF / XLSX / PPTX / HWPX)

사용법:
    python doc_generator.py --summary summaries/파일.md --topic 회의 --type docx
"""

from __future__ import annotations

import sys
# P02: UTF8-FORCE — Windows cp949 인코딩 오류 방지
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import argparse
import logging
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 폰트 탐색 헬퍼
# ---------------------------------------------------------------------------

_FONT_CANDIDATES = [
    # Windows 맑은고딕
    r"C:\Windows\Fonts\malgun.ttf",
    r"C:\Windows\Fonts\malgunbd.ttf",
    # 나눔고딕 (설치된 경우)
    r"C:\Windows\Fonts\NanumGothic.ttf",
    r"C:\Windows\Fonts\NanumGothicBold.ttf",
    # 바탕 계열
    r"C:\Windows\Fonts\batang.ttc",
    # Linux / Mac
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/System/Library/Fonts/AppleGothic.ttf",
]

_FONT_NAME_CANDIDATES = ["맑은 고딕", "Malgun Gothic", "나눔고딕", "NanumGothic", "Batang"]


def _find_font_path() -> Optional[str]:
    """시스템에서 사용 가능한 첫 번째 한국어 폰트 경로를 반환합니다."""
    for p in _FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


# ---------------------------------------------------------------------------
# Markdown 파서
# ---------------------------------------------------------------------------

def _parse_markdown(md_text: str) -> list[dict]:
    """
    Markdown 텍스트를 섹션 리스트로 변환합니다.

    Returns:
        [{"level": 1|2, "title": str, "content": str}, ...]
        level 1 = H1(#), level 2 = H2(##), level 0 = 본문(헤딩 없는 첫 블록)
    """
    sections: list[dict] = []
    current: dict | None = None
    content_lines: list[str] = []

    def _flush():
        nonlocal current, content_lines
        if current is not None:
            current["content"] = "\n".join(content_lines).strip()
            sections.append(current)
        elif content_lines:
            # 헤딩 없는 서두 본문
            sections.append({"level": 0, "title": "", "content": "\n".join(content_lines).strip()})
        current = None
        content_lines = []

    for line in md_text.splitlines():
        h1 = re.match(r"^#\s+(.+)$", line)
        h2 = re.match(r"^##\s+(.+)$", line)
        h3 = re.match(r"^###\s+(.+)$", line)

        if h1:
            _flush()
            current = {"level": 1, "title": h1.group(1).strip(), "content": ""}
        elif h2:
            _flush()
            current = {"level": 2, "title": h2.group(1).strip(), "content": ""}
        elif h3:
            _flush()
            current = {"level": 3, "title": h3.group(1).strip(), "content": ""}
        else:
            content_lines.append(line)

    _flush()

    # 빈 섹션 제거
    return [s for s in sections if s["title"] or s["content"]]


# ---------------------------------------------------------------------------
# 메인 클래스
# ---------------------------------------------------------------------------

class DocumentGenerator:
    """LLM 요약 Markdown → 다형식 문서 생성기."""

    DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "documents"

    def generate(
        self,
        summary_md: str,
        topic: str,
        doc_type: str,
        template_path: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> str:
        """
        Parameters
        ----------
        summary_md    : LLM 요약 Markdown 텍스트
        topic         : 문서 주제 (파일명에 사용)
        doc_type      : "docx" | "pdf" | "xlsx" | "pptx" | "hwpx"
        template_path : 템플릿 파일 경로 (선택)
        output_dir    : 출력 디렉토리 (기본: ../data/documents)

        Returns
        -------
        생성된 파일의 절대 경로 문자열
        """
        doc_type = doc_type.lower().strip()
        if doc_type not in {"docx", "pdf", "xlsx", "pptx", "hwpx"}:
            raise ValueError(f"지원하지 않는 doc_type: {doc_type}")

        out_dir = Path(output_dir) if output_dir else self.DEFAULT_OUTPUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y%m%d")
        safe_topic = re.sub(r'[\\/:*?"<>|]', "_", topic)
        output_path = out_dir / f"{date_str}_{safe_topic}.{doc_type}"

        sections = _parse_markdown(summary_md)
        if not sections:
            sections = [{"level": 0, "title": topic, "content": summary_md}]

        dispatch = {
            "docx": self._generate_docx,
            "pdf":  self._generate_pdf,
            "xlsx": self._generate_xlsx,
            "pptx": self._generate_pptx,
            "hwpx": self._generate_hwpx,
        }
        dispatch[doc_type](sections, topic, template_path, str(output_path))

        logger.info("[DocGenerator] 생성 완료: %s", output_path)
        return str(output_path)

    # ------------------------------------------------------------------
    # DOCX
    # ------------------------------------------------------------------

    def _generate_docx(self, sections, topic, template_path, output_path):
        from docx import Document
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        if template_path and Path(template_path).exists():
            doc = Document(template_path)
        else:
            doc = Document()

        # 기본 폰트 설정
        font_name = "맑은 고딕"
        style_normal = doc.styles["Normal"]
        style_normal.font.name = font_name
        style_normal.font.size = Pt(11)

        # 문서 제목
        title_para = doc.add_heading(topic, level=0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in title_para.runs:
            run.font.name = font_name
            run.font.size = Pt(18)
            run.font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)

        doc.add_paragraph()  # 여백

        for sec in sections:
            level = sec.get("level", 0)
            title = sec.get("title", "")
            content = sec.get("content", "")

            if title:
                heading_level = max(1, min(level, 3))
                h = doc.add_heading(title, level=heading_level)
                for run in h.runs:
                    run.font.name = font_name

            if content:
                for line in content.splitlines():
                    stripped = line.strip()
                    if not stripped:
                        continue
                    # 불릿 리스트 감지
                    if stripped.startswith(("- ", "* ", "• ")):
                        p = doc.add_paragraph(stripped[2:], style="List Bullet")
                    elif re.match(r"^\d+\.\s", stripped):
                        p = doc.add_paragraph(re.sub(r"^\d+\.\s", "", stripped), style="List Number")
                    else:
                        p = doc.add_paragraph(stripped)
                    for run in p.runs:
                        run.font.name = font_name
                        run.font.size = Pt(11)

        doc.save(output_path)

    # ------------------------------------------------------------------
    # PDF
    # ------------------------------------------------------------------

    def _generate_pdf(self, sections, topic, template_path, output_path):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        )
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        # 한국어 폰트 등록
        font_path = _find_font_path()
        font_name = "Korean"
        if font_path:
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
            except Exception as e:
                logger.warning("폰트 등록 실패(%s): %s — 기본 폰트 사용", font_path, e)
                font_name = "Helvetica"
        else:
            logger.warning("한국어 폰트를 찾지 못했습니다. 기본 폰트 사용.")
            font_name = "Helvetica"

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )

        styles = getSampleStyleSheet()

        style_title = ParagraphStyle(
            "KoTitle",
            fontName=font_name,
            fontSize=20,
            leading=28,
            alignment=1,  # CENTER
            textColor=colors.HexColor("#1F497D"),
            spaceAfter=12,
        )
        style_h1 = ParagraphStyle(
            "KoH1",
            fontName=font_name,
            fontSize=14,
            leading=20,
            textColor=colors.HexColor("#2E4057"),
            spaceBefore=12,
            spaceAfter=6,
            borderPad=2,
        )
        style_h2 = ParagraphStyle(
            "KoH2",
            fontName=font_name,
            fontSize=12,
            leading=18,
            textColor=colors.HexColor("#444444"),
            spaceBefore=8,
            spaceAfter=4,
        )
        style_body = ParagraphStyle(
            "KoBody",
            fontName=font_name,
            fontSize=10,
            leading=16,
            spaceAfter=4,
        )
        style_bullet = ParagraphStyle(
            "KoBullet",
            fontName=font_name,
            fontSize=10,
            leading=16,
            leftIndent=12,
            spaceAfter=2,
        )

        story = []
        story.append(Paragraph(topic, style_title))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1F497D")))
        story.append(Spacer(1, 8 * mm))

        for sec in sections:
            level = sec.get("level", 0)
            title = sec.get("title", "")
            content = sec.get("content", "")

            if title:
                style = style_h1 if level <= 1 else style_h2
                story.append(Paragraph(title, style))

            if content:
                for line in content.splitlines():
                    stripped = line.strip()
                    if not stripped:
                        story.append(Spacer(1, 3 * mm))
                        continue
                    if stripped.startswith(("- ", "* ", "• ")):
                        story.append(Paragraph("• " + stripped[2:], style_bullet))
                    elif re.match(r"^\d+\.\s", stripped):
                        story.append(Paragraph(stripped, style_bullet))
                    else:
                        story.append(Paragraph(stripped, style_body))

            story.append(Spacer(1, 4 * mm))

        doc.build(story)

    # ------------------------------------------------------------------
    # XLSX
    # ------------------------------------------------------------------

    def _generate_xlsx(self, sections, topic, template_path, output_path):
        from openpyxl import Workbook, load_workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        if template_path and Path(template_path).exists():
            wb = load_workbook(template_path)
            ws = wb.active
        else:
            wb = Workbook()
            ws = wb.active

        ws.title = topic[:31]  # 시트명 최대 31자

        header_font = Font(name="맑은 고딕", bold=True, size=11, color="FFFFFF")
        header_fill = PatternFill(fill_type="solid", fgColor="1F497D")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        body_font = Font(name="맑은 고딕", size=10)
        body_align = Alignment(vertical="top", wrap_text=True)
        thin_side = Side(style="thin", color="CCCCCC")
        cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

        # 헤더 행
        headers = ["섹션", "내용"]
        for col_idx, h in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = cell_border
        ws.row_dimensions[1].height = 22

        row = 2
        for sec in sections:
            title = sec.get("title", "") or "(서두)"
            content = sec.get("content", "")

            cell_title = ws.cell(row=row, column=1, value=title)
            cell_title.font = Font(name="맑은 고딕", size=10, bold=True)
            cell_title.alignment = body_align
            cell_title.border = cell_border

            cell_body = ws.cell(row=row, column=2, value=content)
            cell_body.font = body_font
            cell_body.alignment = body_align
            cell_body.border = cell_border

            row += 1

        # 열 너비 자동 조정
        col_widths = {1: 30, 2: 80}
        for col_idx, width in col_widths.items():
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        # 제목 행 고정
        ws.freeze_panes = "A2"

        wb.save(output_path)

    # ------------------------------------------------------------------
    # PPTX
    # ------------------------------------------------------------------

    def _generate_pptx(self, sections, topic, template_path, output_path):
        from pptx import Presentation
        from pptx.util import Inches, Pt, Emu
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN

        if template_path and Path(template_path).exists():
            prs = Presentation(template_path)
        else:
            prs = Presentation()

        # 슬라이드 크기: 16:9
        prs.slide_width = Inches(13.33)
        prs.slide_height = Inches(7.5)

        ACCENT = RGBColor(0x1F, 0x49, 0x7D)
        DARK = RGBColor(0x33, 0x33, 0x33)
        LIGHT_BG = RGBColor(0xF2, 0xF2, 0xF2)

        def _set_font(run, size_pt, bold=False, color=None):
            run.font.name = "맑은 고딕"
            run.font.size = Pt(size_pt)
            run.font.bold = bold
            if color:
                run.font.color.rgb = color

        # --- 표지 슬라이드 ---
        slide_layouts = prs.slide_layouts
        # 레이아웃 0: 제목 슬라이드 (일반적으로)
        try:
            title_layout = slide_layouts[0]
        except IndexError:
            title_layout = slide_layouts[0]

        slide0 = prs.slides.add_slide(title_layout)

        # 배경 직사각형
        from pptx.util import Inches
        bg = slide0.shapes.add_shape(
            1,  # MSO_SHAPE_TYPE.RECTANGLE
            Inches(0), Inches(0),
            prs.slide_width, prs.slide_height,
        )
        bg.fill.solid()
        bg.fill.fore_color.rgb = ACCENT
        bg.line.fill.background()
        bg.zorder = 0

        # 제목 텍스트 박스
        txBox = slide0.shapes.add_textbox(
            Inches(1), Inches(2.5), Inches(11.33), Inches(2)
        )
        tf = txBox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = topic
        _set_font(run, 36, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))

        # 날짜
        date_box = slide0.shapes.add_textbox(
            Inches(1), Inches(5), Inches(11.33), Inches(0.5)
        )
        tf2 = date_box.text_frame
        p2 = tf2.paragraphs[0]
        p2.alignment = PP_ALIGN.CENTER
        run2 = p2.add_run()
        run2.text = datetime.now().strftime("%Y년 %m월 %d일")
        _set_font(run2, 14, color=RGBColor(0xCC, 0xDD, 0xFF))

        # --- 섹션 슬라이드 ---
        try:
            content_layout = slide_layouts[1]
        except IndexError:
            content_layout = slide_layouts[0]

        for sec in sections:
            title = sec.get("title", "")
            content = sec.get("content", "").strip()
            if not title and not content:
                continue

            slide = prs.slides.add_slide(content_layout)

            # 헤더 바
            header_bar = slide.shapes.add_shape(
                1,
                Inches(0), Inches(0),
                prs.slide_width, Inches(1.2),
            )
            header_bar.fill.solid()
            header_bar.fill.fore_color.rgb = ACCENT
            header_bar.line.fill.background()

            # 섹션 제목
            title_box = slide.shapes.add_textbox(
                Inches(0.4), Inches(0.15), Inches(12.5), Inches(0.9)
            )
            tf = title_box.text_frame
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = title or "(내용)"
            _set_font(run, 20, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))

            # 본문 텍스트 박스
            body_box = slide.shapes.add_textbox(
                Inches(0.5), Inches(1.4),
                Inches(12.33), Inches(5.8),
            )
            body_tf = body_box.text_frame
            body_tf.word_wrap = True

            first = True
            for line in content.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                if first:
                    para = body_tf.paragraphs[0]
                    first = False
                else:
                    para = body_tf.add_paragraph()

                is_bullet = stripped.startswith(("- ", "* ", "• "))
                is_numbered = bool(re.match(r"^\d+\.\s", stripped))

                if is_bullet:
                    text = stripped[2:]
                    para.level = 1
                elif is_numbered:
                    text = stripped
                    para.level = 1
                else:
                    text = stripped
                    para.level = 0

                run = para.add_run()
                run.text = ("• " + text) if is_bullet else text
                _set_font(run, 13 if para.level == 0 else 11, color=DARK)

        prs.save(output_path)

    # ------------------------------------------------------------------
    # HWPX
    # ------------------------------------------------------------------

    def _generate_hwpx(self, sections, topic, template_path, output_path):
        """
        HWPX 는 ZIP 기반 XML 포맷입니다.
        최소 구조: mimetype / META-INF/container.xml /
                   Contents/header.xml / Contents/section0.xml
        """
        import zipfile

        MIMETYPE = "application/hwp+zip"

        CONTAINER_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<container>
  <rootfiles>
    <rootfile full-path="Contents/header.xml"
              media-type="application/xml"/>
  </rootfiles>
</container>
"""

        HEADER_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"
         version="5.0.4.0">
  <hh:docInfo>
    <hh:title>{title}</hh:title>
  </hh:docInfo>
  <hh:refList>
    <hh:paraShapeList>
      <hh:paraShape id="0" marginLeft="0" marginRight="0"
                    marginTop="0" marginBottom="0"
                    lineSpacing="160" lineSpacingType="percent"/>
    </hh:paraShapeList>
    <hh:charShapeList>
      <hh:charShape id="0" height="1000" textColor="000000"
                    fontRef="0"/>
    </hh:charShapeList>
    <hh:fontList>
      <hh:font id="0" face="맑은 고딕" type="TTF"/>
    </hh:fontList>
  </hh:refList>
  <hh:mappingTable>
    <hh:bodyTextList>
      <hh:item start="0" length="1" name="section0.xml"/>
    </hh:bodyTextList>
  </hh:mappingTable>
</hh:head>
""".format(title=self._xml_escape(topic))

        def _make_para(text: str, bold: bool = False, size: int = 1000) -> str:
            """단순 단락 XML 생성."""
            escaped = self._xml_escape(text)
            bold_attr = 'bold="1"' if bold else ""
            return (
                f'<hp:p xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
                f'<hp:run><hp:charShape charShapeId="0" height="{size}" {bold_attr}/>'
                f'<hp:t>{escaped}</hp:t></hp:run></hp:p>\n'
            )

        body_parts = []
        # 문서 제목
        body_parts.append(_make_para(topic, bold=True, size=1600))
        body_parts.append(_make_para(""))  # 빈 줄

        for sec in sections:
            title = sec.get("title", "")
            content = sec.get("content", "")

            if title:
                body_parts.append(_make_para(title, bold=True, size=1200))

            if content:
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped:
                        body_parts.append(_make_para(stripped))
                    else:
                        body_parts.append(_make_para(""))

            body_parts.append(_make_para(""))

        section_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">\n'
            + "".join(body_parts)
            + "</hs:sec>\n"
        )

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # mimetype 은 압축하지 않고 첫 번째로 (EPUB 규격 준수)
            zf.writestr(
                zipfile.ZipInfo("mimetype"), MIMETYPE,
                compress_type=zipfile.ZIP_STORED,
            )
            zf.writestr("META-INF/container.xml", CONTAINER_XML)
            zf.writestr("Contents/header.xml", HEADER_XML)
            zf.writestr("Contents/section0.xml", section_xml)

    # ------------------------------------------------------------------
    # 유틸
    # ------------------------------------------------------------------

    @staticmethod
    def _xml_escape(text: str) -> str:
        """XML 특수문자 이스케이프."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="LLM 요약 → 문서 생성기")
    parser.add_argument("--summary", required=True, help="요약 Markdown 파일 경로")
    parser.add_argument("--topic", required=True, help="문서 주제 (파일명 사용)")
    parser.add_argument(
        "--type", dest="doc_type", default="docx",
        choices=["docx", "pdf", "xlsx", "pptx", "hwpx"],
        help="출력 문서 형식 (기본: docx)",
    )
    parser.add_argument("--template", default=None, help="템플릿 파일 경로 (선택)")
    parser.add_argument("--output-dir", default=None, help="출력 디렉토리 (선택)")
    args = parser.parse_args()

    summary_path = Path(args.summary)
    if not summary_path.exists():
        print(f"[오류] 요약 파일을 찾을 수 없습니다: {summary_path}", flush=True)
        raise SystemExit(1)

    summary_md = summary_path.read_text(encoding="utf-8")

    gen = DocumentGenerator()
    output = gen.generate(
        summary_md=summary_md,
        topic=args.topic,
        doc_type=args.doc_type,
        template_path=args.template,
        output_dir=args.output_dir,
    )
    print(f"[완료] 문서 생성: {output}", flush=True)


if __name__ == "__main__":
    main()
