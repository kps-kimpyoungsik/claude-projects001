package com.aegis.pm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import com.aegis.pm.dataset.DashboardService;
import com.aegis.pm.dataset.DatasetWriter;

/**
 * 위젯 집계 검증 — 대시보드가 "무엇을(지표) × 어떻게(뷰)"로 나뉘어 있으므로,
 * 뷰가 늘어나도 깨지면 안 되는 것은 지표 계산이다. 그 계산만 값으로 못박는다.
 *
 * 6행짜리 표를 하나 만들어 두고 건수·합계·평균·진척율·분류 트리·추이를 한 번에 확인한다.
 */
@SpringBootTest(properties = {
        "wbs.source=excel",
        "wbs.import-on-start=false",
        "spring.datasource.url=jdbc:h2:mem:dashtest;DB_CLOSE_DELAY=-1",
        "spring.sql.init.mode=always"
})
class DashboardAggregateTest {

    private static final String DS = "DS-TEST-AGG";

    @Autowired DatasetWriter writer;
    @Autowired DashboardService dashboards;

    /** 영역(2종) × 상태(완료 3 / 대기 2 / 처리중 1) × 점수 · 완료일 */
    @BeforeEach
    void 표_준비() {
        List<String> headers = List.of("영역", "화면", "상태", "점수", "완료일");
        List<Map<String, String>> rows = new ArrayList<>();
        rows.add(row(headers, "기준정보", "코드관리", "완료", "10", "2026-09-03"));
        rows.add(row(headers, "기준정보", "권한관리", "완료", "20", "2026-09-11"));
        rows.add(row(headers, "기준정보", "권한관리", "대기", "30", "2026-10-02"));
        rows.add(row(headers, "자금관리", "이체", "완료", "40", "2026-10-15"));
        rows.add(row(headers, "자금관리", "이체", "대기", "", "2026-11-01"));
        rows.add(row(headers, "자금관리", "조회", "처리중", "50", ""));
        writer.write(DS, "집계검증", "sheet1", "test.xlsx", "B-TEST", headers, rows);
    }

    @Test
    void 건수_합계_평균() {
        List<Map<String, Object>> w = render(
                widget("kpi", "전체", "count", "", Map.of()),
                widget("kpi", "점수합계", "sum", "점수", Map.of()),
                widget("kpi", "점수평균", "avg", "점수", Map.of()));

        assertEquals(6.0, num(w.get(0), "total"));                 // 6행
        assertEquals("건", w.get(0).get("unit"));
        assertEquals(150.0, num(w.get(1), "total"));               // 10+20+30+40+50 (빈칸 제외)
        assertEquals(30.0, num(w.get(2), "total"));                // 150 / 5 — 빈칸은 평균에서 빠진다
    }

    @Test
    void 진척율은_판정값_일치행_비율() {
        Map<String, Object> all = render(
                widget("kpi", "전체 진척율", "ratio", "상태", Map.of("match", "완료"))).get(0);
        assertEquals(3.0, num(all, "part"));                       // 완료 3건
        assertEquals(50.0, num(all, "percent"));                   // 3/6
        assertEquals("%", all.get("unit"));
        assertEquals(50.0, num(all, "total"), "진척율의 대표값은 건수가 아니라 비율");
        assertEquals(6.0, num(all, "rowCount"));

        // 분류를 주면 분류마다 진척율이 나온다 (기준정보 2/3, 자금관리 1/3)
        Map<String, Object> byArea = render(
                widget("progress", "영역별 진척율", "ratio", "상태",
                        Map.of("match", "완료", "group", "영역"))).get(0);
        Map<String, Double> pct = pctByName(byArea);
        assertEquals(66.67, pct.get("기준정보"), 0.01);
        assertEquals(33.33, pct.get("자금관리"), 0.01);
    }

    @Test
    void 분류_2단_트리와_점유율() {
        Map<String, Object> w = render(
                widget("group", "영역→화면", "count", "",
                        Map.of("group", "영역", "group2", "화면"))).get(0);

        List<Map<String, Object>> items = items(w);
        assertEquals(2, items.size());
        for (Map<String, Object> it : items) {
            assertEquals(3.0, num(it, "value"), "영역별 3건씩: " + it.get("name"));
            assertEquals(50.0, num(it, "percent"), "점유율 3/6");
        }
        // 기준정보 하위 = 코드관리 1 + 권한관리 2 (하위 점유율은 상위 값 기준)
        Map<String, Object> base = items.stream()
                .filter(i -> "기준정보".equals(i.get("name"))).findFirst().orElseThrow();
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> kids = (List<Map<String, Object>>) base.get("children");
        assertEquals(2, kids.size());
        assertEquals("권한관리", kids.get(0).get("name"));         // 많은 순
        assertEquals(2.0, num(kids.get(0), "value"));
        assertEquals(66.67, num(kids.get(0), "percent"), 0.01);
    }

    @Test
    void 추이는_월별_오름차순_읽을수없는날짜는_제외() {
        Map<String, Object> w = render(
                widget("trend", "완료일 추이", "count", "", Map.of("group", "완료일"))).get(0);

        List<Map<String, Object>> items = items(w);
        assertEquals(List.of("2026-09", "2026-10", "2026-11"),
                items.stream().map(i -> String.valueOf(i.get("name"))).toList());
        assertEquals(2.0, num(items.get(0), "value"));             // 09월 2건
        assertEquals(2.0, num(items.get(1), "value"));             // 10월 2건
        assertEquals(1.0, num(items.get(2), "value"));             // 11월 1건 (빈 날짜 1건은 빠진다)
    }

    @Test
    void 상위N_초과분은_기타로_묶인다() {
        Map<String, Object> w = render(
                widget("bar", "화면 분포", "count", "", Map.of("group", "화면", "top", 1))).get(0);

        List<Map<String, Object>> items = items(w);
        assertEquals(2, items.size());
        assertEquals(2.0, num(items.get(0), "value"));             // 최다 1종만 남고
        assertTrue(String.valueOf(items.get(1).get("name")).startsWith("기타"));
        assertEquals(4.0, num(items.get(1), "value"));             // 나머지 4건 합
    }

    @Test
    void 목표값을_주면_그_기준으로_비율을_낸다() {
        Map<String, Object> w = render(
                widget("progress", "목표 대비", "count", "", Map.of("target", 12))).get(0);
        assertEquals(50.0, num(w, "percent"));                     // 6 / 12
    }

    /** 뷰마다 폭·높이가 반드시 채워져 내려간다 — 레이아웃이 span 없이 무너지지 않게 */
    @Test
    void 모든_위젯에_폭과_높이가_채워진다() {
        List<Map<String, Object>> w = render(
                widget("kpi", "a", "count", "", Map.of()),
                widget("table", "b", "", "", Map.of()),
                widget("group", "c", "count", "", Map.of("group", "영역", "w", 99, "h", 0)));

        for (Map<String, Object> x : w) {
            @SuppressWarnings("unchecked")
            Map<String, Object> o = (Map<String, Object>) x.get("options");
            double width = num(o, "w");
            double height = num(o, "h");
            assertTrue(width >= 1 && width <= 12, "폭 범위 이탈: " + width);
            assertTrue(height >= 1 && height <= 6, "높이 범위 이탈: " + height);
            assertNull(x.get("error"), "집계 실패: " + x.get("error"));
        }
    }

    // ── 도우미 ──────────────────────────────────────────────────────────────

    @SafeVarargs
    private List<Map<String, Object>> render(Map<String, Object>... specs) {
        Map<String, Object> out = dashboards.preview(List.of(specs));
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> widgets = (List<Map<String, Object>>) out.get("widgets");
        return widgets;
    }

    private static Map<String, Object> widget(String kind, String title, String agg, String col,
                                              Map<String, Object> options) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("kind", kind);
        m.put("title", title);
        m.put("datasetId", DS);
        m.put("agg", agg);
        m.put("col", col);
        m.put("options", new LinkedHashMap<>(options));
        return m;
    }

    private static Map<String, String> row(List<String> headers, String... vals) {
        Map<String, String> m = new LinkedHashMap<>();
        for (int i = 0; i < headers.size(); i++) m.put(headers.get(i), i < vals.length ? vals[i] : "");
        return m;
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> items(Map<String, Object> w) {
        return (List<Map<String, Object>>) w.get("items");
    }

    private static Map<String, Double> pctByName(Map<String, Object> w) {
        Map<String, Double> m = new LinkedHashMap<>();
        for (Map<String, Object> it : items(w)) m.put(String.valueOf(it.get("name")), num(it, "percent"));
        return m;
    }

    private static double num(Map<String, Object> m, String k) {
        Object v = m.get(k);
        return v instanceof Number n ? n.doubleValue() : Double.NaN;
    }
}
