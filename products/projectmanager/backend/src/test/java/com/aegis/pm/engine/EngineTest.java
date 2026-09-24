package com.aegis.pm.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;

/**
 * 범용 규칙 발견 엔진 — 도메인 단어 없이 값의 통계만으로 판단하는지. 컬럼명은 일부러 의미 없는 이름(A·B·C)을 쓴다:
 * 이름을 읽어서 맞히는 규칙이면 이 테스트를 통과할 수 없다.
 */
class EngineTest {

    private static List<String> row(String... v) {
        return new ArrayList<>(List.of(v));
    }

    @Test
    void 제목_행을_건너뛰고_진짜_헤더를_고른다() {
        List<List<String>> g = new ArrayList<>();
        g.add(row("2026년 3분기 현황", "", "", ""));          // 제목 — 한 칸
        g.add(row("", "", "", ""));
        g.add(row("A", "B", "C", "D"));                       // 헤더
        for (int i = 0; i < 20; i++) g.add(row("X-" + i, String.valueOf(100 + i), "2026-09-" + (10 + i % 9), i % 2 == 0 ? "가" : "나"));
        HeaderDetector.Result r = HeaderDetector.detect(g);
        assertEquals(2, r.row(), r.evidence());
    }

    @Test
    void 제목과_메타_행_아래의_진짜_헤더를_고른다() {
        // 실측 형태(WBS_Raw): 1행 제목, 2행 "기준일 : 2026-09-01 · 계획 : …" 메타, 3행 헤더 — 이전 방식은 2행을 헤더로 삼았다
        List<List<String>> g = new ArrayList<>();
        g.add(row("프로젝트 전체 일정", "", "", "", ""));
        g.add(row("기준일 :", "2026-09-01", "계획 :", "67%", ""));
        g.add(row("No", "Code", "Dep", "Name", "Rate"));
        for (int i = 0; i < 30; i++) g.add(row(String.valueOf(i + 1), "C-" + (1000 + i), String.valueOf(i % 3 + 1), "작업 항목 " + i, String.valueOf(i * 3 % 100)));
        assertEquals(2, HeaderDetector.detect(g).row(), HeaderDetector.detect(g).evidence());
    }

    @Test
    void 한_시트에_표가_여럿이면_위쪽_표를_유지한다() {
        List<List<String>> g = new ArrayList<>();
        g.add(row("A", "B", "C"));
        for (int i = 0; i < 6; i++) g.add(row("K" + i, String.valueOf(i * 10), String.valueOf(i)));
        g.add(row("", "", ""));
        g.add(row("P", "Q", "R"));
        for (int i = 0; i < 30; i++) g.add(row("M" + i, String.valueOf(i * 7), String.valueOf(i % 4)));
        assertEquals(0, HeaderDetector.detect(g).row(), "요약표 아래 상세표가 근소하게 이겨도 위쪽 표를 둔다");
    }

    @Test
    void 헤더가_없는_표는_첫_행을_데이터로_둔다() {
        // 실측 형태(WBS_미완료): 첫 행부터 데이터 — 이전 방식은 첫 행을 헤더로 삼았다
        List<List<String>> g = new ArrayList<>();
        for (int i = 0; i < 23; i++) g.add(row(String.valueOf(i + 1), "WBS-" + (100 + i), i % 3 == 0 ? "공통" : "여신", "작업 " + i, String.valueOf(40 + i)));
        HeaderDetector.Result r = HeaderDetector.detect(g);
        assertFalse(r.hasHeader(), r.evidence());
    }

    @Test
    void 역할은_이름이_아니라_값의_분포로_정한다() {
        assertEquals("time", RoleModel.prior(DataProfiler.profile(List.of("2026-09-01", "2026-09-02", "2026.9.3", "2026/09/04"))).role());
        assertEquals("time", RoleModel.prior(DataProfiler.profile(List.of("46000", "46010", "46023", "46100"))).role(), "엑셀 일련번호");
        assertEquals("measure", RoleModel.prior(DataProfiler.profile(List.of("1,200", "35", "8.5", "400", "12"))).role());
        assertEquals("id", RoleModel.prior(DataProfiler.profile(List.of("K-01", "K-02", "K-03", "K-04", "K-05"))).role());
        List<String> cat = new ArrayList<>();
        for (int i = 0; i < 40; i++) cat.add(i % 3 == 0 ? "대기" : i % 3 == 1 ? "진행" : "완료");
        assertEquals("category", RoleModel.prior(DataProfiler.profile(cat)).role());
        List<String> prose = new ArrayList<>();
        for (int i = 0; i < 12; i++) prose.add("이 칸에는 " + i + "번째 설명 문장이 길게 들어간다. 예시와 기준을 함께 적는다.");
        assertEquals("text", RoleModel.prior(DataProfiler.profile(prose)).role(), "긴 문장은 값이 전부 달라도 식별자가 아니다");
        assertEquals("person", RoleModel.prior(DataProfiler.profile(List.of("PII-0123456789ab", "PII-aaaaaaaaaaaa", "PII-0123456789ab"))).role());
    }

    @Test
    void 사람_라벨이_쌓이면_학습된_판단이_사전_규칙을_이긴다() {
        // 사전 규칙은 이 분포(짧은 코드 3종 반복)를 category 로 본다. 사람이 5번 "id" 라고 고치면 그쪽을 따른다
        List<String> codes = new ArrayList<>();
        for (int i = 0; i < 30; i++) codes.add("C" + (i % 3));
        DataProfiler.Profile p = DataProfiler.profile(codes);
        assertEquals("category", new RoleModel(List.of()).guess(p).role());
        List<RoleModel.Label> labels = new ArrayList<>();
        for (int k = 0; k < 5; k++) labels.add(new RoleModel.Label(p.vector(), "id"));
        RoleModel.Guess g = new RoleModel(labels).guess(p);
        assertEquals("id", g.role());
        assertTrue(g.evidence().startsWith("학습"), g.evidence());
    }

    @Test
    void 정제_계획은_값의_성질에서_나오고_적용은_원본을_바꾸지_않는다() {
        List<String> h = List.of("A", "B", "C", "E");
        List<Map<String, String>> rows = new ArrayList<>();
        for (int i = 0; i < 10; i++) {
            Map<String, String> r = new LinkedHashMap<>();
            r.put("A", " K-" + i + "  ");
            r.put("B", i == 3 ? "-" : String.valueOf(46000 + i));
            r.put("C", i == 5 ? "1,500" : String.valueOf(10 + i));
            rows.add(r);
        }
        rows.add(new LinkedHashMap<>(rows.get(0)));   // 중복 행
        Map<String, String> roles = Map.of("A", "id", "B", "time", "C", "measure", "E", "text");
        List<RefinePlanner.Op> ops = RefinePlanner.plan(h, rows, roles);
        List<String> kinds = ops.stream().map(RefinePlanner.Op::op).toList();
        assertTrue(kinds.containsAll(List.of("DROP_EMPTY_COLUMN", "TRIM_SPACE", "NORMALIZE_NULL", "DATE_SERIAL_TO_ISO",
                "NUMBER_UNFORMAT", "DEDUPE_ROWS")), kinds.toString());

        String before = rows.toString();
        Map<String, Object> out = RefinePlanner.apply(h, rows, ops);
        assertEquals(before, rows.toString(), "원본은 그대로");
        @SuppressWarnings("unchecked")
        List<Map<String, String>> r2 = (List<Map<String, String>>) out.get("rows");
        assertEquals(10, r2.size(), "중복 1행 제거");
        assertFalse(((List<?>) out.get("headers")).contains("E"), "빈 열 제거");
        assertEquals("K-0", r2.get(0).get("A"));
        assertEquals("2025-12-09", r2.get(0).get("B"), "일련번호 46000 → 날짜");
        assertFalse(r2.get(3).containsKey("B"), "결측 표기 '-' → 빈 값");
        assertEquals("1500", r2.get(5).get("C"));
    }
}
