package com.aegis.pm.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import com.aegis.pm.dataset.DatasetIngestService;
import com.aegis.pm.dataset.DatasetWriter;

/**
 * 자료 보존형 정형화 — 사라진 것은 이력에 남고, 사람이 복원·직접 수정하면 정제본이 다시 만들어지는가
 * (plans/_opens/data_lineage_review).
 */
@SpringBootTest(properties = {
        "wbs.source=excel",
        "wbs.import-on-start=false",
        "spring.datasource.url=jdbc:h2:mem:lineage;DB_CLOSE_DELAY=-1",
        "spring.sql.init.mode=always"
})
class LineageTest {

    @Autowired DatasetIngestService ingest;
    @Autowired DatasetWriter writer;
    @Autowired EngineService engine;
    @Autowired JdbcTemplate jdbc;

    @BeforeEach
    void reset() {
        for (String t : List.of("refine_trace", "refine_decision", "dataset_qualification", "dataset_facet", "dataset_binding",
                "dataset_row", "dataset_column", "dataset")) {
            jdbc.update("DELETE FROM " + t);
        }
    }

    private static void row(Sheet s, int r, String... v) {
        Row x = s.createRow(r);
        for (int c = 0; c < v.length; c++) if (v[c] != null) x.createCell(c).setCellValue(v[c]);
    }

    @Test
    void 적재에서_버린_제목_행은_이력에_남고_헤더_밖_칸은_보존된다() throws Exception {
        try (XSSFWorkbook wb = new XSSFWorkbook()) {
            Sheet s = wb.createSheet("시트");
            row(s, 0, "분기 현황 보고");
            row(s, 2, "Code", "Qty", "Note");
            for (int i = 0; i < 12; i++) row(s, 3 + i, "C-" + i, String.valueOf(i * 10), "메모" + i, i == 4 ? "헤더밖" : null);
            ingest.ingestSheet("DS-T1", "시트", s, "t.xlsx", null);
        }
        List<Map<String, Object>> t = (List<Map<String, Object>>) engine.traces("DS-T1").get("traces");
        assertTrue(t.stream().anyMatch(x -> "PRE_HEADER_ROW".equals(x.get("op")) && "분기 현황 보고".equals(x.get("before_v"))), t.toString());
        // 헤더 폭 밖의 칸은 버리지 않는다 — 격자가 최대 폭으로 채워져 자동 이름 열(col4)로 들어간다
        assertEquals("헤더밖", writer.rows("DS-T1").get(4).get("col4"));
    }

    @Test
    void 복원하면_정제본에_돌아오고_직접_수정은_원본에_이력과_함께_남는다() {
        List<String> h = List.of("Code", "Qty");
        List<Map<String, String>> rows = new ArrayList<>();
        for (int i = 0; i < 12; i++) rows.add(new LinkedHashMap<>(Map.of("Code", "C-" + i, "Qty", i == 3 ? "N/A" : String.valueOf(i * 10))));
        writer.write("DS-T2", "재고", "재고", "t.xlsx", null, h, rows);

        engine.apply("DS-T2");
        assertFalse(writer.rows("DS-T2-R").get(3).containsKey("Qty"), "결측 표기는 정제에서 빈 값");
        List<Map<String, Object>> t = (List<Map<String, Object>>) engine.traces("DS-T2-R").get("traces");
        assertTrue(t.stream().anyMatch(x -> "NORMALIZE_NULL".equals(x.get("op")) && "N/A".equals(x.get("before_v"))), t.toString());

        engine.restore("DS-T2-R", "NORMALIZE_NULL", "Qty", 3);
        assertEquals("N/A", writer.rows("DS-T2-R").get(3).get("Qty"), "복원 결정 → 정제본 재생성 시 유지");
        engine.apply("DS-T2-R");
        assertEquals("N/A", writer.rows("DS-T2-R").get(3).get("Qty"), "다시 정제해도 사람 결정은 유지");

        Map<String, Object> e = engine.edit("DS-T2-R", 3, "Qty", "35");
        assertEquals("N/A", e.get("before"));
        assertEquals("35", writer.rows("DS-T2").get(3).get("Qty"), "직접 수정은 원본에");
        assertEquals("35", writer.rows("DS-T2-R").get(3).get("Qty"), "정제본은 다시 만들어진다");
        List<Map<String, Object>> edits = (List<Map<String, Object>>) engine.traces("DS-T2").get("traces");
        assertTrue(edits.stream().anyMatch(x -> "MANUAL_EDIT".equals(x.get("op")) && "N/A".equals(x.get("before_v"))), "되돌릴 수 있게 이전 값 보존");

        writer.write("DS-T2", "재고", "재고", "t.xlsx", null, h, writer.rows("DS-T2"));
        assertTrue(((List<?>) engine.traces("DS-T2").get("traces")).size() >= 1, "재저장해도 직접 수정 이력은 남는다");
    }

    @Autowired com.aegis.pm.dds.QualificationService cqg;

    @Test
    void 헤더_없는_표는_규모_미달로_격리되지_않는다() {
        List<Map<String, String>> rows = new ArrayList<>();
        for (int i = 0; i < 10; i++) rows.add(new LinkedHashMap<>(Map.of("col1", String.valueOf(i + 1), "col2", "WBS-" + i, "col3", "작업 " + i)));
        writer.write("DS-NH", "헤더 없음", "s", "t.xlsx", null, List.of("col1", "col2", "col3"), rows);
        String reason = (String) cqg.evaluate("DS-NH").get("reason");
        assertFalse(reason.startsWith("규모"), reason);
        assertTrue(reason.contains("헤더 없음"), reason);
    }

    @Test
    void 같은_양식을_더_올리면_한_묶음이_되고_재검증된다() {
        List<String> h = List.of("Code", "State", "Qty");
        for (int f = 0; f < 3; f++) {
            List<Map<String, String>> rows = new ArrayList<>();
            for (int i = 0; i < 6; i++) rows.add(new LinkedHashMap<>(Map.of("Code", "C" + f + i, "State", i % 2 == 0 ? "대기" : "완료", "Qty", String.valueOf(i))));
            writer.write("DS-G" + f, "주간" + f, "주간", "w" + f + ".xlsx", null, h, rows);
        }
        writer.write("DS-X", "다른 양식", "x", "x.xlsx", null, List.of("Title", "Body"),
                List.of(new LinkedHashMap<>(Map.of("Title", "a", "Body", "b"))));

        List<Map<String, Object>> groups = engine.groups();
        assertEquals(2, groups.size(), "묶음 수는 자료가 정한다");
        Map<String, Object> g = groups.stream().filter(x -> ((Number) x.get("size")).intValue() == 3).findFirst().orElseThrow();
        assertEquals(18, ((Number) g.get("rows")).intValue());

        Map<String, Object> rv = engine.reverify((String) g.get("group"));
        assertEquals(3, rv.get("members"));
    }
}
