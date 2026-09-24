package com.aegis.pm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import com.aegis.pm.dataset.DashboardService;
import com.aegis.pm.dataset.DatasetWriter;
import com.aegis.pm.dds.FacetService;
import com.aegis.pm.dds.QualificationService;
import com.aegis.pm.dds.StandardSeeder;
import com.aegis.pm.pii.PiiRegistry;

/**
 * DDS 패싯(P3)·CQG 자격 게이트(P4). 판정 기준은 운영 DB 복사본 전수 평가에서 나온 오판정을 고정한 것이다
 * (WBS 빈 꼬리 열 · 엑셀 일련번호 날짜 · 가이드 시트 대체 규칙 — plans/_dones/dds_facet_cqg/ 참조).
 */
@SpringBootTest(properties = {
        "wbs.source=excel",
        "wbs.import-on-start=false",
        "spring.datasource.url=jdbc:h2:mem:ddsquality;DB_CLOSE_DELAY=-1",
        "spring.sql.init.mode=always"
})
class DdsQualityTest {

    @Autowired DatasetWriter writer;
    @Autowired FacetService facets;
    @Autowired QualificationService cqg;
    @Autowired DashboardService dashboards;
    @Autowired StandardSeeder seeder;
    @Autowired JdbcTemplate jdbc;

    @BeforeEach
    void reset() {
        for (String t : List.of("dataset_qualification", "dataset_facet", "dataset_binding", "binding_feedback",
                "dataset_row", "dataset_column", "dataset")) {
            jdbc.update("DELETE FROM " + t);
        }
        seeder.seed();
    }

    private static List<Map<String, String>> rows(List<String> h, int n, java.util.function.BiFunction<String, Integer, String> v) {
        List<Map<String, String>> out = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            Map<String, String> r = new LinkedHashMap<>();
            for (String c : h) r.put(c, v.apply(c, i));
            out.add(r);
        }
        return out;
    }

    private String verdict(String id) {
        return (String) cqg.current(id).get("verdict");
    }

    @Test
    void 적재하면_바인딩_패싯_판정이_자동으로_붙는다() {
        List<String> h = List.of("결함ID", "등록일", "결함상태", "결함내용", "심각도", "담당자");
        writer.write("DS-D", "결함", "결함대장", "f.xlsx", "UP-1", h, rows(h, 12, (c, i) -> switch (c) {
            case "결함ID" -> "D-" + i;
            case "등록일" -> "2026-09-" + (10 + i);
            case "결함상태" -> i % 2 == 0 ? "대기" : "완료";
            case "심각도" -> i % 3 == 0 ? "높음" : "보통";
            case "담당자" -> "담당" + (i % 3);
            default -> "로그인 오류 " + i;
        }));
        assertTrue(jdbc.queryForObject("SELECT COUNT(*) FROM dataset_binding WHERE dataset_id='DS-D'", Integer.class) > 0, "바인딩");
        assertEquals("결함", jdbc.queryForObject(
                "SELECT facet_value FROM dataset_facet WHERE dataset_id='DS-D' AND axis='domain'", String.class), "분야");
        assertEquals("time", role("DS-D", "등록일"));
        assertEquals("status", role("DS-D", "결함상태"));
        assertEquals("person", role("DS-D", "담당자"));
        assertEquals("QUALIFIED", verdict("DS-D"));
    }

    private String role(String ds, String col) {
        return jdbc.queryForObject("SELECT facet_value FROM dataset_facet WHERE dataset_id=? AND axis='role' AND col_name=?",
                String.class, ds, col);
    }

    @Test
    void 규모_하한_미달은_점수_없이_격리되고_목록에서_숨는다() {
        List<String> h = List.of("항목", "값");
        writer.write("DS-C", "표지", "표지", "f.xlsx", null, h, rows(h, 2, (c, i) -> c + i));
        assertEquals("REJECTED", verdict("DS-C"));
        assertEquals(0, ((Number) cqg.current("DS-C").get("score")).intValue());
        assertFalse(dashboards.datasets(false).stream().anyMatch(d -> "DS-C".equals(d.get("dataset_id"))), "격리는 목록에서 숨김");
        assertTrue(dashboards.datasets(true).stream().anyMatch(d -> "DS-C".equals(d.get("dataset_id"))), "?all=true 면 보인다");
        assertEquals(2, jdbc.queryForObject("SELECT COUNT(*) FROM dataset_row WHERE dataset_id='DS-C'", Integer.class),
                "격리는 삭제가 아니다");
    }

    @Test
    void 가이드_시트는_격리되고_빈_꼬리_열은_멀쩡한_표를_격리시키지_않는다() {
        List<String> g = List.of("항목", "설명");
        writer.write("DS-G", "작성가이드", "작성가이드", "f.xlsx", "UP-2", g,
                rows(g, 18, (c, i) -> c.equals("항목") ? "항목 " + i : "이 칸에는 " + i + "번째 규칙을 적는다. 예시를 참고한다."));
        assertEquals("REJECTED", verdict("DS-G"), "설명 문장 열이 id·status 로 점수를 받으면 안 된다: " + cqg.current("DS-G"));

        // WBS 실측 형태: 날짜가 엑셀 일련번호(숫자) + 끝에 완전히 빈 열 7개
        List<String> w = new ArrayList<>(List.of("WBS ID", "작업명", "담당자", "시작예정일", "종료예정일", "진행률(%)", "상태"));
        for (int k = 21; k <= 27; k++) w.add("col" + k);
        writer.write("DS-W", "WBS", "WBS", "f.xlsx", "UP-3", w, rows(w, 40, (c, i) -> switch (c) {
            case "WBS ID" -> "WBS-" + i;
            case "작업명" -> "작업 " + i;
            case "담당자" -> "담당" + (i % 4);
            case "시작예정일" -> String.valueOf(46000 + i);
            case "종료예정일" -> String.valueOf(46010 + i);
            case "진행률(%)" -> String.valueOf(i % 100);
            case "상태" -> i % 2 == 0 ? "진행" : "완료";
            default -> "";
        }));
        assertEquals("time", role("DS-W", "시작예정일"), "엑셀 일련번호 날짜");
        assertFalse(verdict("DS-W").equals("REJECTED"), "빈 꼬리 열 때문에 격리되면 안 된다: " + cqg.current("DS-W"));
        assertTrue(jdbc.queryForObject("SELECT COUNT(*) FROM dataset_facet WHERE dataset_id='DS-W' AND axis='context'"
                + " AND facet_value = '기준일=2026-01-27'", Integer.class) == 1,
                "기준일은 날짜로 보인다(일련번호 46049 가 아니라 2026-01-27)");
    }

    @Test
    void HTML_조각이나_긴_문장은_유효한_헤더가_아니다() {
        assertFalse(com.aegis.pm.dds.QualificationService.validHeader("<li class=\"form-item\"> <input name=\"x\">"));
        assertFalse(com.aegis.pm.dds.QualificationService.validHeader("col21"));
        assertFalse(com.aegis.pm.dds.QualificationService.validHeader("가".repeat(41)));
        assertTrue(com.aegis.pm.dds.QualificationService.validHeader("진행률(%)"));
    }

    @Test
    void 사람이_뒤집은_판정은_재평가가_덮지_않는다() {
        List<String> h = List.of("항목", "값");
        writer.write("DS-O", "x", "x", "f.xlsx", null, h, rows(h, 2, (c, i) -> c + i));
        cqg.override("DS-O", "QUALIFIED", "tester");
        cqg.evaluate("DS-O");
        assertEquals("QUALIFIED", verdict("DS-O"));
        cqg.release("DS-O");
        assertEquals("REJECTED", verdict("DS-O"), "해제하면 자동 판정");
    }

    @Test
    void 사람이_정한_분야는_재분류가_덮지_않는다() {
        List<String> h = List.of("결함ID", "결함상태", "심각도");
        writer.write("DS-H", "x", "x", "f.xlsx", null, h, rows(h, 5, (c, i) -> c + i));
        facets.setHuman("DS-H", "domain", null, "인프라");
        facets.classify("DS-H");
        assertEquals(List.of("인프라"), jdbc.queryForList(
                "SELECT facet_value FROM dataset_facet WHERE dataset_id='DS-H' AND axis='domain'", String.class));
    }

    @Test
    void 계정_비밀정보는_적재되지_않는다() {
        List<String> h = List.of("구분", "id / pwd : web_dev / 1234", "비고");
        writer.write("DS-S", "서버정보", "서버정보", "f.xlsx", null, h, List.of(
                Map.of("구분", "DB", "id / pwd : web_dev / 1234", "id / pwd : sa / Secret9!", "비고", "재배포"),
                Map.of("구분", "WAS", "id / pwd : web_dev / 1234", "pwd: Another1!", "비고", "로그")));
        String all = String.join("", jdbc.queryForList("SELECT payload FROM dataset_row WHERE dataset_id='DS-S'", String.class))
                + String.join("", jdbc.queryForList("SELECT COALESCE(name,'') || COALESCE(min_v,'') || COALESCE(max_v,'') FROM dataset_column WHERE dataset_id='DS-S'", String.class));
        assertFalse(all.contains("Secret9!") || all.contains("Another1!") || all.contains("web_dev"), all);
        assertTrue(all.contains(PiiRegistry.SECRET_BLOCKED));
        assertTrue(all.contains("재배포"), "비밀정보 아닌 칸은 그대로");
    }
}
