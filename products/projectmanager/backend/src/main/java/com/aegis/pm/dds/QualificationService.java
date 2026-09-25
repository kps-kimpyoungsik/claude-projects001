package com.aegis.pm.dds;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.aegis.pm.common.Rows;

/**
 * DDS Phase 4 CQG — 이 표가 <b>데이터셋일 가치가 있는가</b> (06 §2). 8지표 100점 + 규모 하한.
 *
 * <pre>
 *   ≥70 QUALIFIED · 40~69 PROVISIONAL(보완 필요) · &lt;40 REJECTED(격리 — 목록에서 숨김, 행은 그대로)
 *   규모 하한: 데이터 행 &lt; 3 또는 유효 컬럼 &lt; 2 → 점수 계산 없이 REJECTED
 * </pre>
 *
 * 지표는 전부 기존 산출물(컬럼 프로파일·어휘 사전·표준 바인딩·패싯)을 다시 읽는다 — 새 추론 0.
 * 사람이 뒤집은 판정(override_by)은 재평가가 덮지 않는다.
 */
@Service
public class QualificationService {

    static final int QUALIFIED = 70, PROVISIONAL = 40;
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    /** 잘린 표·자동 생성 헤더 — 유효 컬럼이 아니다 */
    private static final Pattern BAD_HEADER = Pattern.compile("^(Column\\s*\\d+|Unnamed.*|열\\s*\\d+|col_?\\d+|\\d+|-)?$",
            Pattern.CASE_INSENSITIVE);
    /** 의도를 알 수 없는 시트명 — 엑셀 기본값 */
    private static final Pattern DEFAULT_SHEET = Pattern.compile("^(Sheet\\s*\\d*|시트\\s*\\d*|Sheet)$", Pattern.CASE_INSENSITIVE);

    private final JdbcTemplate jdbc;
    private final VocabStore vocab;
    private final ObjectMapper json = new ObjectMapper();

    private final com.aegis.pm.engine.EngineService engine;

    public QualificationService(JdbcTemplate jdbc, VocabStore vocab, com.aegis.pm.engine.EngineService engine) {
        this.jdbc = jdbc;
        this.vocab = vocab;
        this.engine = engine;
    }

    @Transactional
    public Map<String, Object> evaluate(String datasetId) {
        List<Map<String, Object>> ds = Rows.lower(jdbc.queryForList("SELECT * FROM dataset WHERE dataset_id = ?", datasetId));
        if (ds.isEmpty()) throw new IllegalArgumentException("데이터셋이 없습니다: " + datasetId);
        Map<String, Object> prev = current(datasetId);
        if (prev != null && prev.get("override_by") != null) {
            prev.put("skipped", "사람이 정한 판정 — 재평가하지 않음");
            return prev;
        }
        Map<String, Object> d = ds.get(0);
        int rows = num(d.get("row_count"));
        List<Map<String, Object>> cols = Rows.lower(jdbc.queryForList(
                "SELECT name, null_n FROM dataset_column WHERE dataset_id = ? ORDER BY col_no", datasetId));
        List<Map<String, Object>> facets = Rows.lower(jdbc.queryForList(
                "SELECT axis, facet_value, col_name, confidence FROM dataset_facet WHERE dataset_id = ?", datasetId));

        // 완전히 빈 열은 표의 일부가 아니다 — 분모에 넣으면 잘린 표의 빈 꼬리가 멀쩡한 표를 격리시킨다
        // (실측: WBS 시트 27열 중 7열이 43행 전부 공란 → 39점 REJECTED)
        cols = cols.stream().filter(c -> rows == 0 || num(c.get("null_n")) < rows).toList();
        int valid = (int) cols.stream().filter(c -> validHeader(str(c.get("name")))).count();
        Map<String, Object> bd = new LinkedHashMap<>();
        String verdict, reason;
        int score;
        // 규모는 값이 있는 컬럼 수로 본다 — 이름 없는 컬럼(헤더 없는 표의 col1…)도 자료다. 이름으로 세면 헤더 없는 표가
        // 통째로 격리됐다(실측 2026-09-25: WBS_미완료 재적재 후 24행 · 유효 0개 → 0점). 이름이 없는 것은 구조 점수가 깎는다
        if (rows < 3 || cols.size() < 2) {
            score = 0;
            verdict = "REJECTED";
            reason = "규모 하한 미달 — 데이터 " + rows + "행 · 값 있는 컬럼 " + cols.size() + "개 (최소 3행 · 2개)";
            bd.put("scale", reason);
        } else {
            int n = cols.size();
            // 1 단어 의미 — 헤더가 어휘 사전에 있는 비율 (기록 없는 조회: 재평가가 통계를 부풀리지 않게)
            long lex = cols.stream().filter(c -> vocab.peek(str(c.get("name"))) != null).count();
            double s1 = 15.0 * lex / n;
            // 2 맥락 — 출처·배치·기준일
            long ctx = facets.stream().filter(f -> "context".equals(f.get("axis"))).count();
            double s2 = 10.0 * Math.min(3, ctx) / 3;
            // 3 구조 — 유효 헤더율 × (1 - 결측률)
            long nulls = cols.stream().mapToLong(c -> num(c.get("null_n"))).sum();
            double missing = (double) nulls / ((long) rows * n);
            double s3 = 15.0 * ((double) valid / n) * (1 - Math.min(1, missing));
            // 엔진이 "헤더가 데이터처럼 보인다"고 판정하면(헤더 값이 열에 또 나옴·숫자/날짜 헤더) 컬럼명이 없는 표다 —
            // 구조 점수를 주지 않는다(실측: WBS_미완료 가 날짜 열 발견으로 격리를 벗어남)
            boolean headerSuspect = Boolean.TRUE.equals(engine.profile(datasetId).get("headerSuspect"));
            if (headerSuspect) s3 = 0;
            // 4 주제 응집 — 이 표의 컬럼 중 한 표준으로 설명되는 비율 (표 쪽에서 본 바인딩)
            Integer bound = jdbc.queryForObject("SELECT COUNT(*) FROM dataset_binding WHERE dataset_id = ?", Integer.class, datasetId);
            double s4 = 10.0 * Math.min(1, (bound == null ? 0 : bound) / (double) n);
            // 5 의미·역할 — role 이 text 가 아닌 컬럼 비율
            long roles = facets.stream().filter(f -> "role".equals(f.get("axis")) && !"text".equals(f.get("facet_value"))).count();
            double s5 = 15.0 * roles / n;
            // 6 기능 — 분야 판정 확신도
            double dom = facets.stream().filter(f -> "domain".equals(f.get("axis")))
                    .mapToDouble(f -> f.get("confidence") == null ? 0 : ((Number) f.get("confidence")).doubleValue()).max().orElse(0);
            double s6 = 10.0 * Math.min(1, dom);
            // 7 방향성 — 시간 축 · 상태 축
            boolean time = facets.stream().anyMatch(f -> "role".equals(f.get("axis")) && "time".equals(f.get("facet_value")));
            // 상태 축 = 적은 종류가 반복되는 범주 열(엔진 판정). "상태어" 단어 목록은 쓰지 않는다
            boolean status = facets.stream().anyMatch(f -> "role".equals(f.get("axis")) && "category".equals(f.get("facet_value")));
            double s7 = (time ? 5 : 0) + (status ? 5 : 0);
            // 8 의도 — 시트명 유의미 · 출처 파일 · 표준 바인딩
            String sheet = str(d.get("sheet_name")).trim();
            double s8 = (!sheet.isEmpty() && !DEFAULT_SHEET.matcher(sheet).matches() ? 5 : 0)
                    + (d.get("source_file") != null ? 5 : 0) + (d.get("std_id") != null ? 5 : 0);

            bd.put("lexical", r(s1));
            bd.put("context", r(s2));
            bd.put("structure", r(s3));
            bd.put("topic", r(s4));
            bd.put("role", r(s5));
            bd.put("function", r(s6));
            bd.put("direction", r(s7));
            bd.put("intent", r(s8));
            score = (int) Math.round(s1 + s2 + s3 + s4 + s5 + s6 + s7 + s8);
            verdict = score >= QUALIFIED ? "QUALIFIED" : score >= PROVISIONAL ? "PROVISIONAL" : "REJECTED";
            reason = rows + "행 · 컬럼 " + n + "개(유효 " + valid + ") · 사전 " + lex + " · 바인딩 " + (bound == null ? 0 : bound)
                    + (headerSuspect ? " · 헤더 의심(재적재 권장)" : "")
                    + (valid == 0 ? " · 헤더 없음(컬럼 이름 지정 필요)" : "")
                    + (time ? " · 시간축" : "") + (status ? " · 상태축" : "");
        }
        String now = LocalDateTime.now().format(TS);
        jdbc.update("DELETE FROM dataset_qualification WHERE dataset_id = ?", datasetId);
        jdbc.update("""
                INSERT INTO dataset_qualification (dataset_id, verdict, score, breakdown, reason, quarantined, evaluated_at)
                VALUES (?,?,?,?,?,?,?)""", datasetId, verdict, score, write(bd), reason, "REJECTED".equals(verdict), now);
        return current(datasetId);
    }

    public Map<String, Object> evaluateAll() {
        int q = 0, p = 0, x = 0, skipped = 0;
        for (String id : jdbc.queryForList("SELECT dataset_id FROM dataset ORDER BY dataset_id", String.class)) {
            Map<String, Object> r = evaluate(id);
            if (r.containsKey("skipped")) { skipped++; continue; }
            switch (String.valueOf(r.get("verdict"))) {
                case "QUALIFIED" -> q++;
                case "PROVISIONAL" -> p++;
                default -> x++;
            }
        }
        return Map.of("qualified", q, "provisional", p, "rejected", x, "overridden", skipped);
    }

    /** 사람이 뒤집는다 — 자동 재평가가 다시 덮지 않는다 (06 §2.3) */
    @Transactional
    public Map<String, Object> override(String datasetId, String verdict, String by) {
        if (!List.of("QUALIFIED", "PROVISIONAL", "REJECTED").contains(verdict)) throw new IllegalArgumentException("판정: QUALIFIED · PROVISIONAL · REJECTED");
        if (current(datasetId) == null) evaluate(datasetId);
        jdbc.update("""
                UPDATE dataset_qualification SET verdict = ?, quarantined = ?, override_by = ?, override_at = ?
                 WHERE dataset_id = ?""", verdict, "REJECTED".equals(verdict), by == null || by.isBlank() ? "human" : by,
                LocalDateTime.now().format(TS), datasetId);
        return current(datasetId);
    }

    /** 사람 판정을 풀고 자동 판정으로 되돌린다 */
    @Transactional
    public Map<String, Object> release(String datasetId) {
        jdbc.update("UPDATE dataset_qualification SET override_by = NULL, override_at = NULL WHERE dataset_id = ?", datasetId);
        return evaluate(datasetId);
    }

    public Map<String, Object> current(String datasetId) {
        List<Map<String, Object>> r = Rows.lower(jdbc.queryForList("SELECT * FROM dataset_qualification WHERE dataset_id = ?", datasetId));
        return r.isEmpty() ? null : r.get(0);
    }

    public List<Map<String, Object>> list() {
        return Rows.lower(jdbc.queryForList("""
                SELECT q.*, d.name, d.sheet_name, d.source_file, d.row_count, d.col_count
                  FROM dataset_qualification q JOIN dataset d ON d.dataset_id = q.dataset_id
                 ORDER BY q.score, q.dataset_id"""));
    }

    /**
     * 컬럼명으로 쓸 수 있는가 — 자동 생성 이름·빈칸이 아니고, 40자 이하이며 HTML 이 아니다.
     * 40자·'<' 기준은 PiiRegistry.kindOfHeader 와 같다(실측: HTML 가이드 시트의 180자 &lt;li …&gt; 조각이 헤더로 잡힘).
     */
    public static boolean validHeader(String h) {
        String t = h == null ? "" : h.trim();
        return !BAD_HEADER.matcher(t).matches() && t.length() <= 40 && t.indexOf('<') < 0;
    }

    private String write(Map<String, Object> m) {
        try {
            return json.writeValueAsString(m);
        } catch (Exception e) {
            return "{}";
        }
    }

    private static double r(double v) {
        return Math.round(v * 10) / 10.0;
    }

    private static int num(Object o) {
        return o == null ? 0 : ((Number) o).intValue();
    }

    private static String str(Object o) {
        return o == null ? "" : String.valueOf(o);
    }
}
