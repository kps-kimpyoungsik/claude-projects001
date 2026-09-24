package com.aegis.pm.source;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.function.Consumer;

import org.apache.poi.openxml4j.opc.OPCPackage;
import org.apache.poi.openxml4j.opc.PackageAccess;
import org.apache.poi.ss.usermodel.DataFormatter;
import org.apache.poi.util.XMLHelper;
import org.apache.poi.xssf.eventusermodel.ReadOnlySharedStringsTable;
import org.apache.poi.xssf.eventusermodel.XSSFReader;
import org.apache.poi.xssf.eventusermodel.XSSFSheetXMLHandler;
import org.apache.poi.xssf.model.StylesTable;
import org.apache.poi.xssf.usermodel.XSSFComment;
import org.apache.poi.xslf.usermodel.XMLSlideShow;
import org.apache.poi.xslf.usermodel.XSLFGroupShape;
import org.apache.poi.xslf.usermodel.XSLFShape;
import org.apache.poi.xslf.usermodel.XSLFSlide;
import org.apache.poi.xslf.usermodel.XSLFTable;
import org.apache.poi.xslf.usermodel.XSLFTextShape;
import org.apache.poi.xwpf.usermodel.IBodyElement;
import org.apache.poi.xwpf.usermodel.XWPFDocument;
import org.apache.poi.xwpf.usermodel.XWPFParagraph;
import org.apache.poi.xwpf.usermodel.XWPFTable;
import org.xml.sax.InputSource;
import org.xml.sax.XMLReader;

/**
 * USS L2 EXTRACT — 어떤 파일이든 <b>조각(fragment) + 원본 좌표(locator)</b>로 편다.
 *
 * <p>정형화(L3)는 여기서 하지 않는다. 이 층의 약속은 하나뿐이다:
 * <b>나중에 어떤 값이 나오든, 그 값이 원본 어디에서 왔는지 되짚을 수 있다</b>(불변식 I1).
 *
 * <h3>locator — 포맷별 테이블을 나누지 않고 문자열 1개 (ADR U-A3)</h3>
 * <pre>
 *   sheet:견적!C5        xlsx 셀
 *   docx:p12             docx 본문 12번째 문단
 *   docx:t1.r3.c2        docx 1번째 표 3행 2열
 *   pptx:s2.sh4          pptx 2번 슬라이드 4번째 도형
 *   pptx:s2.sh4.r1.c1    pptx 도형이 표일 때 셀
 *   txt:L7 / md:L7       7번째 줄
 *   image:whole / audio:whole / pdf:whole   원본 통째 (아직 추출기 없음)
 * </pre>
 *
 * <h3>이미지·음성·pdf — 받되, 지어내지 않는다</h3>
 * 원본은 보관하고 조각 1개(kind=image|audio|binary, text=null, confidence=0)만 남긴다.
 * OCR/STT 없이 텍스트를 채우면 "출처는 있는데 틀린 근거"가 된다(뼈대 §12 OCR 보류 사유).
 * ponytail: 추출 엔진이 하나도 없어서 포트(interface)를 두지 않았다 — 첫 OCR/STT/PDFBox 엔진이
 * 붙는 날 {@code extract()} 의 해당 분기를 {@code MediaExtractor} 포트로 뽑는다.
 */
public final class Extractor {

    private Extractor() {}

    /** 조각 1개. text 가 null 이면 "원본은 있으나 아직 읽지 못함" */
    public record Fragment(String locator, String kind, String text, double confidence) {}

    static final Set<String> OFFICE = Set.of("xlsx", "docx", "pptx");
    static final Set<String> TEXT = Set.of("txt", "md", "csv");
    static final Set<String> IMAGE = Set.of("png", "jpg", "jpeg", "gif", "bmp", "webp", "tif", "tiff");
    static final Set<String> AUDIO = Set.of("mp3", "wav", "m4a", "ogg", "flac", "aac", "webm");
    static final Set<String> BINARY = Set.of("pdf");

    public static String formatOf(String fileName) {
        int dot = fileName.lastIndexOf('.');
        return dot < 0 ? "" : fileName.substring(dot + 1).toLowerCase(Locale.ROOT);
    }

    public static boolean supported(String format) {
        return OFFICE.contains(format) || TEXT.contains(format) || IMAGE.contains(format)
                || AUDIO.contains(format) || BINARY.contains(format);
    }

    public static List<Fragment> extract(Path file, String format) throws Exception {
        List<Fragment> out = new ArrayList<>();
        extract(file, format, out::add);
        return out;
    }

    /** 조각을 모으지 않고 흘려보낸다 — 큰 시트를 메모리에 다 올리지 않기 위해 적재는 이쪽을 쓴다 */
    public static void extract(Path file, String format, Consumer<Fragment> sink) throws Exception {
        if (IMAGE.contains(format)) { sink.accept(new Fragment("image:whole", "image", null, 0)); return; }
        if (AUDIO.contains(format)) { sink.accept(new Fragment("audio:whole", "audio", null, 0)); return; }
        if (BINARY.contains(format)) { sink.accept(new Fragment(format + ":whole", "binary", null, 0)); return; }
        switch (format) {
            case "xlsx" -> xlsx(file, sink);
            case "docx" -> docx(file).forEach(sink);
            case "pptx" -> pptx(file).forEach(sink);
            case "txt", "md", "csv" -> lines(file, format).forEach(sink);
            default -> throw new IllegalArgumentException("지원하지 않는 형식: " + format);
        }
    }

    /**
     * xlsx 는 SAX 스트리밍으로 읽는다. {@code XSSFWorkbook}(DOM)은 50,000행×10열(1.7MB)에서
     * 힙 512MB 를 넘겼다(실측 2026-09-23 OOM) — 업로드 한도 30MB 면 서버가 죽는다.
     * ponytail: docx·pptx 는 아직 DOM — 텍스트 문서는 셀 폭증이 없어 같은 한도에서 문제가 실측되면 전환.
     */
    private static void xlsx(Path file, Consumer<Fragment> sink) throws Exception {
        try (OPCPackage pkg = OPCPackage.open(file.toFile(), PackageAccess.READ)) {
            XSSFReader reader = new XSSFReader(pkg);
            ReadOnlySharedStringsTable strings = new ReadOnlySharedStringsTable(pkg);
            StylesTable styles = reader.getStylesTable();
            XSSFReader.SheetIterator it = (XSSFReader.SheetIterator) reader.getSheetsData();
            while (it.hasNext()) {
                try (InputStream in = it.next()) {
                    String prefix = "sheet:" + it.getSheetName() + "!";
                    XMLReader xml = XMLHelper.newXMLReader();
                    xml.setContentHandler(new XSSFSheetXMLHandler(styles, null, strings,
                            new XSSFSheetXMLHandler.SheetContentsHandler() {
                                @Override public void startRow(int rowNum) {}
                                @Override public void endRow(int rowNum) {}
                                @Override public void cell(String ref, String value, XSSFComment comment) {
                                    String v = value == null ? "" : value.strip();
                                    if (!v.isEmpty()) sink.accept(new Fragment(prefix + ref, "cell", v, 1));
                                }
                            }, new DataFormatter(), false));
                    xml.parse(new InputSource(in));
                }
            }
        }
    }

    private static List<Fragment> docx(Path file) throws Exception {
        List<Fragment> out = new ArrayList<>();
        try (InputStream in = Files.newInputStream(file); XWPFDocument doc = new XWPFDocument(in)) {
            int p = 0, t = 0;
            for (IBodyElement el : doc.getBodyElements()) {
                if (el instanceof XWPFParagraph para) {
                    p++;
                    String v = para.getText().strip();
                    if (!v.isEmpty()) out.add(new Fragment("docx:p" + p, "text", v, 1));
                } else if (el instanceof XWPFTable table) {
                    table(table, "docx:t" + (++t), out);
                }
            }
        }
        return out;
    }

    /**
     * 셀 텍스트는 셀 안의 <b>문단만</b> 모은다 — {@code XWPFTableCell.getText()} 는 표 안의 표를
     * 빼먹는다(실측 2026-09-23, 테스트로 고정). 중첩 표는 자기 좌표로 따로 나온다.
     */
    private static void table(XWPFTable table, String base, List<Fragment> out) {
        for (int r = 0; r < table.getNumberOfRows(); r++) {
            var cells = table.getRow(r).getTableCells();
            for (int c = 0; c < cells.size(); c++) {
                String loc = base + ".r" + (r + 1) + ".c" + (c + 1);
                StringBuilder sb = new StringBuilder();
                int nt = 0;
                for (IBodyElement el : cells.get(c).getBodyElements()) {
                    if (el instanceof XWPFParagraph para && !para.getText().isBlank()) {
                        if (sb.length() > 0) sb.append('\n');
                        sb.append(para.getText().strip());
                    } else if (el instanceof XWPFTable inner) {
                        table(inner, loc + ".t" + (++nt), out);
                    }
                }
                if (sb.length() > 0) out.add(new Fragment(loc, "cell", sb.toString(), 1));
            }
        }
    }

    private static List<Fragment> pptx(Path file) throws Exception {
        List<Fragment> out = new ArrayList<>();
        try (InputStream in = Files.newInputStream(file); XMLSlideShow ppt = new XMLSlideShow(in)) {
            List<XSLFSlide> slides = ppt.getSlides();
            for (int s = 0; s < slides.size(); s++) {
                shapes(slides.get(s).getShapes(), "pptx:s" + (s + 1) + ".sh", out);
            }
        }
        return out;
    }

    /** 그룹 도형은 안으로 들어간다 — 안 들어가면 그룹 속 텍스트가 조용히 사라진다. locator: pptx:s1.sh2.sh1 */
    private static void shapes(List<XSLFShape> shapes, String prefix, List<Fragment> out) {
        for (int h = 0; h < shapes.size(); h++) {
            String base = prefix + (h + 1);
            XSLFShape shape = shapes.get(h);
            if (shape instanceof XSLFTextShape ts) {
                String v = ts.getText().strip();
                if (!v.isEmpty()) out.add(new Fragment(base, "text", v, 1));
            } else if (shape instanceof XSLFGroupShape g) {
                shapes(g.getShapes(), base + ".sh", out);
            } else if (shape instanceof XSLFTable table) {
                for (int r = 0; r < table.getNumberOfRows(); r++) {
                    var cells = table.getRows().get(r).getCells();
                    for (int c = 0; c < cells.size(); c++) {
                        String v = cells.get(c).getText().strip();
                        if (!v.isEmpty()) {
                            out.add(new Fragment(base + ".r" + (r + 1) + ".c" + (c + 1), "cell", v, 1));
                        }
                    }
                }
            }
        }
    }

    /** 줄 단위. 한국어 문서가 많아 UTF-8 우선, BOM 은 떼어낸다 */
    private static List<Fragment> lines(Path file, String format) throws Exception {
        String prefix = format.equals("csv") ? "txt" : format;
        String all = new String(Files.readAllBytes(file), StandardCharsets.UTF_8);
        if (all.startsWith("﻿")) all = all.substring(1);
        if (all.indexOf('�') >= 0) {
            // UTF-8 이 아닌 파일(CP949 등)을 UTF-8 로 읽으면 바이트를 버린다 — 깨진 채 저장하지 않는다
            throw new IllegalArgumentException("텍스트 인코딩이 UTF-8 이 아닙니다 — UTF-8 로 저장해 다시 올리십시오.");
        }
        List<Fragment> out = new ArrayList<>();
        String[] ls = all.split("\r?\n", -1);
        for (int i = 0; i < ls.length; i++) {
            String v = ls[i].strip();
            if (!v.isEmpty()) out.add(new Fragment(prefix + ":L" + (i + 1), "text", v, 1));
        }
        return out;
    }
}
