package com.aegis.pm.source;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import org.apache.poi.xslf.usermodel.XMLSlideShow;
import org.apache.poi.xslf.usermodel.XSLFTextBox;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.apache.poi.xwpf.usermodel.XWPFDocument;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockMultipartFile;

/**
 * USS U1 통과 기준(뼈대 §14): <b>같은 내용의 xlsx·docx·pptx·txt 4개에서 동일 항목이 조각으로 나오고,
 * locator 로 원본 위치를 되짚는다.</b> + 같은 원본 재업로드는 조각을 두 벌 만들지 않는다(T115)
 * + 모든 적재는 case_usage 를 남긴다(G1).
 */
@SpringBootTest(properties = {
        "wbs.source=excel",
        "wbs.import-on-start=false",
        "spring.datasource.url=jdbc:h2:mem:sourcetest;DB_CLOSE_DELAY=-1",
        "spring.sql.init.mode=always"
})
class SourceExtractTest {

    static final List<String> ITEMS = List.of("견적번호", "Q-2026-001", "합계금액", "1,200,000");

    @TempDir Path dir;
    @Autowired SourceService service;
    @Autowired com.aegis.pm.upload.UploadService uploads;
    @Autowired JdbcTemplate jdbc;

    private Path xlsx() throws Exception {
        Path p = dir.resolve("a.xlsx");
        try (XSSFWorkbook wb = new XSSFWorkbook(); OutputStream out = Files.newOutputStream(p)) {
            var sh = wb.createSheet("견적");
            for (int i = 0; i < ITEMS.size(); i++) sh.createRow(i).createCell(2).setCellValue(ITEMS.get(i));
            wb.write(out);
        }
        return p;
    }

    private Path docx() throws Exception {
        Path p = dir.resolve("a.docx");
        try (XWPFDocument doc = new XWPFDocument(); OutputStream out = Files.newOutputStream(p)) {
            doc.createParagraph().createRun().setText(ITEMS.get(0));
            doc.createParagraph();                                   // 빈 문단 — 조각이 되면 안 된다
            var t = doc.createTable(1, 3);
            for (int c = 0; c < 3; c++) t.getRow(0).getCell(c).setText(ITEMS.get(c + 1));
            doc.write(out);
        }
        return p;
    }

    private Path pptx() throws Exception {
        Path p = dir.resolve("a.pptx");
        try (XMLSlideShow ppt = new XMLSlideShow(); OutputStream out = Files.newOutputStream(p)) {
            var slide = ppt.createSlide();
            for (String s : ITEMS) {
                XSLFTextBox box = slide.createTextBox();
                box.setText(s);
            }
            ppt.write(out);
        }
        return p;
    }

    private Path txt() throws Exception {
        Path p = dir.resolve("a.txt");
        Files.writeString(p, "﻿" + String.join("\n\n", ITEMS), StandardCharsets.UTF_8);
        return p;
    }

    @Test
    void 같은_내용의_네_형식에서_같은_항목이_좌표와_함께_나온다() throws Exception {
        Map<String, Path> files = Map.of("xlsx", xlsx(), "docx", docx(), "pptx", pptx(), "txt", txt());
        for (var e : files.entrySet()) {
            List<Extractor.Fragment> frags = Extractor.extract(e.getValue(), e.getKey());
            assertEquals(ITEMS, frags.stream().map(Extractor.Fragment::text).toList(), e.getKey());
            assertTrue(frags.stream().allMatch(f -> f.locator().startsWith(e.getKey().equals("xlsx") ? "sheet:" : e.getKey() + ":")),
                    e.getKey() + " locator prefix");
        }
        assertEquals("sheet:견적!C2", Extractor.extract(files.get("xlsx"), "xlsx").get(1).locator());
        assertEquals("docx:t1.r1.c3", Extractor.extract(files.get("docx"), "docx").get(3).locator());
        assertEquals("pptx:s1.sh2", Extractor.extract(files.get("pptx"), "pptx").get(1).locator());
        assertEquals("txt:L3", Extractor.extract(files.get("txt"), "txt").get(1).locator());
    }

    /** 직전 다차원 표의 반례 — 병합 셀·표 안의 표·그룹 도형에서 누락·중복이 없는가 */
    @Test
    void 병합셀_중첩표_그룹도형도_한번씩만_나온다() throws Exception {
        Path x = dir.resolve("m.xlsx");
        try (XSSFWorkbook wb = new XSSFWorkbook(); OutputStream out = Files.newOutputStream(x)) {
            var sh = wb.createSheet("S");
            sh.createRow(0).createCell(0).setCellValue("병합제목");
            sh.addMergedRegion(new org.apache.poi.ss.util.CellRangeAddress(0, 0, 0, 3));
            wb.write(out);
        }
        assertEquals(List.of("병합제목"), texts(x, "xlsx"), "병합 영역은 좌상단 1번만 — 복제되면 값이 네 번 센다");

        Path d = dir.resolve("n.docx");
        try (XWPFDocument doc = new XWPFDocument(); OutputStream out = Files.newOutputStream(d)) {
            var cell = doc.createTable(1, 1).getRow(0).getCell(0);
            cell.setText("바깥");
            var inner = cell.insertNewTbl(cell.addParagraph().getCTP().newCursor());
            inner.getCTTbl().addNewTr().addNewTc().addNewP().addNewR().addNewT().setStringValue("안쪽");
            doc.write(out);
        }
        String nested = String.join("|", texts(d, "docx"));
        assertTrue(nested.contains("바깥") && nested.contains("안쪽"), "표 안의 표 텍스트가 사라지면 안 된다: " + nested);

        Path p = dir.resolve("g.pptx");
        try (XMLSlideShow ppt = new XMLSlideShow(); OutputStream out = Files.newOutputStream(p)) {
            var g = ppt.createSlide().createGroup();
            g.createTextBox().setText("그룹속1");
            g.createTextBox().setText("그룹속2");
            ppt.write(out);
        }
        List<Extractor.Fragment> gf = Extractor.extract(p, "pptx");
        assertEquals(List.of("그룹속1", "그룹속2"), gf.stream().map(Extractor.Fragment::text).toList());
        assertEquals("pptx:s1.sh1.sh2", gf.get(1).locator());
    }

    private static List<String> texts(Path f, String fmt) throws Exception {
        return Extractor.extract(f, fmt).stream().map(Extractor.Fragment::text).toList();
    }

    @Test
    void 이미지와_음성은_원본만_받고_텍스트를_지어내지_않는다() throws Exception {
        Path img = Files.write(dir.resolve("a.png"), new byte[] { 1, 2, 3 });
        var f = Extractor.extract(img, "png").get(0);
        assertEquals("image:whole", f.locator());
        assertNull(f.text(), "OCR 없이 텍스트를 채우면 틀린 근거가 된다");
        assertEquals("audio", Extractor.extract(img, "mp3").get(0).kind());
    }

    @Test
    void 적재_중복제거_사용이력() throws Exception {
        byte[] bytes = Files.readAllBytes(docx());
        Map<String, Object> first = service.ingest(new MockMultipartFile("file", "견적.docx", null, bytes));
        Map<String, Object> again = service.ingest(new MockMultipartFile("file", "견적-사본.docx", null, bytes));
        try {
            assertEquals(false, first.get("duplicate"));
            assertEquals(true, again.get("duplicate"), "같은 sha256 은 기존 문서를 돌려준다");
            assertEquals(first.get("docId"), again.get("docId"));
            String docId = (String) first.get("docId");
            assertEquals(ITEMS.size(), service.fragments(docId, 500).size(), "조각이 두 벌 생기지 않는다");
            assertEquals(2, jdbc.queryForObject(
                    "SELECT COUNT(*) FROM case_usage WHERE node_type='source_doc' AND node_id=?", Integer.class, docId),
                    "재업로드도 사용 이력으로 남는다");
        } finally {
            Files.deleteIfExists(Path.of(jdbc.queryForObject(
                    "SELECT stored_path FROM source_doc WHERE doc_id=?", String.class, first.get("docId"))));
        }
    }

    @Test
    void 기존_엑셀_업로드도_만든_데이터셋을_사용이력에_남긴다() throws Exception {
        Path p = dir.resolve("ds.xlsx");
        try (XSSFWorkbook wb = new XSSFWorkbook(); OutputStream out = Files.newOutputStream(p)) {
            var sh = wb.createSheet("품목");
            String[][] rows = { { "품목", "수량", "단가" }, { "A", "1", "100" }, { "B", "2", "200" } };
            for (int r = 0; r < rows.length; r++) {
                var row = sh.createRow(r);
                for (int c = 0; c < 3; c++) row.createCell(c).setCellValue(rows[r][c]);
            }
            wb.write(out);
        }
        Map<String, Object> res = uploads.upload(new MockMultipartFile("file", "ds.xlsx", null, Files.readAllBytes(p)));
        try {
            assertEquals(1, jdbc.queryForObject(
                    "SELECT COUNT(*) FROM case_usage WHERE case_id=? AND node_type='dataset' AND usage='output'",
                    Integer.class, res.get("batchId")), String.valueOf(res));
        } finally {
            Files.deleteIfExists(Path.of(jdbc.queryForObject(
                    "SELECT stored_path FROM upload_batch WHERE batch_id=?", String.class, res.get("batchId"))));
        }
    }

    @Test
    void 깨진_입력은_거절한다() {
        byte[] cp949 = { (byte) 0xB0, (byte) 0xDF, (byte) 0xC0, (byte) 0xFB };   // "견적" CP949
        assertThrows(IllegalArgumentException.class,
                () -> service.ingest(new MockMultipartFile("file", "a.txt", null, cp949)));
        assertThrows(IllegalArgumentException.class,
                () -> service.ingest(new MockMultipartFile("file", "fake.docx", null, "not zip".getBytes())));
        assertThrows(IllegalArgumentException.class,
                () -> service.ingest(new MockMultipartFile("file", "a.exe", null, new byte[] { 1 })));
    }
}
