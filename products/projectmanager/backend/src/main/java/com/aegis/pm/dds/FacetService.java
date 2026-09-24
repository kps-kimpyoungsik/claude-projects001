package com.aegis.pm.dds;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.aegis.pm.common.Rows;
import com.aegis.pm.pii.PiiRegistry;

/**
 * DDS Phase 3 패싯 — 데이터셋이 <b>무엇에 관한 것인지</b>를 붙인다 (01_설계서 §3). 1단계 축 3개:
 *
 * <pre>
 *   domain  (데이터셋) 바인딩된 표준의 분야 · 확신도 = bind_ratio      — 새 사전 없이 표준을 재사용(하드코딩 금지)
 *   role    (컬럼)     id · time · status · measure · person · text  — dataset_column 통계에서 규칙으로
 *   context (데이터셋) 출처 파일 · 업로드 배치 · 기준일(날짜 컬럼 최댓값)
 * </pre>
 *
 * area(값 매칭)·topic(군집)·link(표 간 관계)는 2단계. {@code source='human'} 은 재분류가 덮지 않는다.
 */
@Service
public class FacetService {

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    /** 상태 컬럼의 표기 — 설계서 §3.1 "상태/여부/구분" + 실측 표기(단계·결과·진행) */
    private static final Pattern STATUS_WORD = Pattern.compile("상태|여부|구분|단계|결과|진행|status", Pattern.CASE_INSENSITIVE);
    /** 날짜 컬럼 표기 — 엑셀은 날짜를 일련번호(숫자)로 주는 경우가 많다(실측: WBS 시작·종료예정일) */
    private static final Pattern DATE_WORD = Pattern.compile("일자|날짜|예정일|완료일|시작일|종료일|등록일|기한|일시|date", Pattern.CASE_INSENSITIVE);
    /** 엑셀 일련번호로 볼 수 있는 범위 — 1954-10 ~ 2119-01 */
    static final double SERIAL_MIN = 20000, SERIAL_MAX = 80000;
    /** 서술형 헤더 — 값이 전부 달라도 식별자가 아니라 본문이다(실측: 가이드 시트 "설명" 열이 id 로 잡힘) */
    private static final Pattern PROSE_WORD = Pattern.compile("설명|내용|비고|메모|참고|예시|가이드|방법|규칙|기준|사유|의견|요약|description|note|memo|remark", Pattern.CASE_INSENSITIVE);
    private static final Pattern ID_WORD = Pattern.compile("ID|번호|코드|No\\.?$|^no$|seq|순번", Pattern.CASE_INSENSITIVE);

    private final JdbcTemplate jdbc;
    private final com.aegis.pm.pii.PiiVault pii;

    public FacetService(JdbcTemplate jdbc, com.aegis.pm.pii.PiiVault pii) {
        this.jdbc = jdbc;
        this.pii = pii;
    }

    /** 데이터셋 1개 재분류 — 사람이 정한 축·컬럼은 그대로 둔다 */
    @Transactional
    public Map<String, Object> classify(String datasetId) {
        List<Map<String, Object>> ds = Rows.lower(jdbc.queryForList("SELECT * FROM dataset WHERE dataset_id = ?", datasetId));
        if (ds.isEmpty()) throw new IllegalArgumentException("데이터셋이 없습니다: " + datasetId);
        Map<String, Object> d = ds.get(0);
        int rowCount = num(d.get("row_count"));
        String now = LocalDateTime.now().format(TS);
        jdbc.update("DELETE FROM dataset_facet WHERE dataset_id = ? AND source <> 'human'", datasetId);

        // role — 컬럼마다
        Map<String, Integer> roles = new LinkedHashMap<>();
        String baseDate = null;
        for (Map<String, Object> c : Rows.lower(jdbc.queryForList(
                "SELECT name, data_type, distinct_n, null_n, min_v, max_v, sum_v FROM dataset_column WHERE dataset_id = ? ORDER BY col_no",
                datasetId))) {
            String col = (String) c.get("name");
            if (num(c.get("null_n")) >= rowCount && rowCount > 0) continue;   // 완전히 빈 열 — 표의 일부가 아니다
            String[] r = role(col, (String) c.get("data_type"), num(c.get("distinct_n")), num(c.get("null_n")),
                    c.get("sum_v"), rowCount, str(c.get("min_v")), str(c.get("max_v")));
            put(datasetId, "role", r[0], "column", col, Double.parseDouble(r[1]), "rule", r[2], now);
            roles.merge(r[0], 1, Integer::sum);
            if ("time".equals(r[0]) && c.get("max_v") != null) {
                String mx = asDate(String.valueOf(c.get("max_v")));
                if (baseDate == null || mx.compareTo(baseDate) > 0) baseDate = mx;
            }
        }

        // domain — 바인딩된 표준의 분야. 바인딩이 없으면 붙이지 않는다(모르는 것을 지어내지 않는다)
        String domain = null;
        double conf = 0;
        Integer humanDomain = jdbc.queryForObject(
                "SELECT COUNT(*) FROM dataset_facet WHERE dataset_id = ? AND axis = 'domain' AND source = 'human'", Integer.class, datasetId);
        if (humanDomain != null && humanDomain > 0) {
            domain = jdbc.queryForObject("SELECT MAX(facet_value) FROM dataset_facet WHERE dataset_id = ? AND axis = 'domain'", String.class, datasetId);
            conf = 1.0;
        } else if (d.get("std_id") != null) {
            List<String> dom = jdbc.queryForList("SELECT domain FROM standard_dataset WHERE std_id = ?", String.class, d.get("std_id"));
            if (!dom.isEmpty() && dom.get(0) != null) {
                domain = dom.get(0);
                conf = d.get("bind_ratio") == null ? 0 : ((Number) d.get("bind_ratio")).doubleValue();
                put(datasetId, "domain", domain, "dataset", null, conf, "rule",
                        d.get("std_id") + " 바인딩 " + Math.round(conf * 100) + "%", now);
            }
        }

        // context — 새 추론 없음(설계서 §3.1): 출처·배치·기준일
        List<String> context = new ArrayList<>();
        if (d.get("source_file") != null) context.add("출처=" + pii.scrub(String.valueOf(d.get("source_file"))));
        if (d.get("batch_id") != null) context.add("배치=" + d.get("batch_id"));
        if (baseDate != null) context.add("기준일=" + baseDate);
        for (String v : context) put(datasetId, "context", v, "dataset", null, 1.0, "rule", "dataset·upload_batch·날짜 컬럼", now);

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("datasetId", datasetId);
        out.put("domain", domain);
        out.put("domainConfidence", conf);
        out.put("roles", roles);
        out.put("context", context);
        return out;
    }

    /**
     * 컬럼 의미 — 설계서 §3.1 규칙. 반환: {role, confidence, 근거}.
     * 순서가 판정을 바꾼다: 사람(person) → 시간 → 상태 → 식별자 → 측정값 → 텍스트.
     */
    static String[] role(String col, String type, int distinct, int nulls, Object sum, int rows, String minV, String maxV) {
        String name = col == null ? "" : col;
        if (PiiRegistry.PERSON.equals(PiiRegistry.kindOfHeader(name))) return new String[] { "person", "0.9", "컬럼명이 사람 표기" };
        if ("date".equals(type)) return new String[] { "time", "0.95", "날짜 타입" };
        if ("number".equals(type) && DATE_WORD.matcher(name).find() && serial(minV) && serial(maxV)) {
            return new String[] { "time", "0.85", "날짜 표기 + 엑셀 일련번호 범위" };
        }
        if ("category".equals(type) && distinct <= 10 && STATUS_WORD.matcher(name).find()) {
            return new String[] { "status", "0.9", "범주 " + distinct + "종 + 상태어" };
        }
        // 긴 텍스트는 값이 전부 달라도 식별자가 아니다 — 설명 문장 열이 id 로 잡혀 가이드 시트가 역할 점수를 받았다(실측)
        if (rows >= 3 && distinct == rows && nulls == 0 && !PROSE_WORD.matcher(name).find()
                && (ID_WORD.matcher(name).find() || "category".equals(type))) {
            return new String[] { "id", "0.85", "고유값 = 행수, 결측 0" };
        }
        if ("number".equals(type) && sum != null) return new String[] { "measure", "0.8", "숫자 + 합계" };
        // 상태어 없는 범주는 status 가 아니다 — 대체 규칙으로 status 를 주면 가이드·범례 시트가 역할·방향성 점수를
        // 거저 받는다(실측: 작성가이드·약어 시트가 역할 15/15 로 격리를 피했다)
        return new String[] { "text", "0.5", "해당 규칙 없음" };
    }

    private static boolean serial(String v) {
        try {
            double d = Double.parseDouble(v);
            return d >= SERIAL_MIN && d <= SERIAL_MAX;
        } catch (RuntimeException e) {
            return false;
        }
    }

    /** 엑셀 일련번호면 yyyy-MM-dd 로 — 기준일이 "46234" 로 보이지 않게 */
    static String asDate(String v) {
        if (!serial(v)) return v;
        return java.time.LocalDate.of(1899, 12, 30).plusDays((long) Double.parseDouble(v)).toString();
    }

    private static String str(Object o) {
        return o == null ? null : String.valueOf(o);
    }

    public List<Map<String, Object>> facets(String datasetId) {
        return Rows.lower(jdbc.queryForList(
                "SELECT axis, facet_value, target_type, col_name, confidence, source, evidence FROM dataset_facet"
                        + " WHERE dataset_id = ? ORDER BY axis, col_name", datasetId));
    }

    /** 사람이 지정 — 이후 자동 재분류가 덮지 않는다. domain 은 데이터셋당 1개, role 은 컬럼당 1개 */
    @Transactional
    public Map<String, Object> setHuman(String datasetId, String axis, String colName, String value) {
        if (!"domain".equals(axis) && !"role".equals(axis)) throw new IllegalArgumentException("사람이 정할 수 있는 축: domain · role");
        if ("role".equals(axis) && (colName == null || colName.isBlank())) throw new IllegalArgumentException("role 은 컬럼을 지정하세요");
        if ("domain".equals(axis)) {
            jdbc.update("DELETE FROM dataset_facet WHERE dataset_id = ? AND axis = 'domain'", datasetId);
        } else {
            jdbc.update("DELETE FROM dataset_facet WHERE dataset_id = ? AND axis = 'role' AND col_name = ?", datasetId, colName);
        }
        put(datasetId, axis, value, "role".equals(axis) ? "column" : "dataset", "role".equals(axis) ? colName : null,
                1.0, "human", "사람 지정", LocalDateTime.now().format(TS));
        return Map.of("ok", true, "datasetId", datasetId, "axis", axis, "value", value);
    }

    private void put(String ds, String axis, String value, String target, String col, double conf, String source,
                     String evidence, String now) {
        String id = ds + "|" + axis + "|" + (col != null ? col : value);
        if (id.length() > 80) id = id.substring(0, 60) + "#" + Integer.toHexString(id.hashCode());
        // 사람이 이미 정한 자리는 비워 두었으므로(위 DELETE 가 human 을 남김) 같은 자리에 규칙이 오면 건너뛴다
        Integer human = jdbc.queryForObject("SELECT COUNT(*) FROM dataset_facet WHERE facet_id = ? AND source = 'human'",
                Integer.class, id);
        if (human != null && human > 0 && !"human".equals(source)) return;
        if ("human".equals(source)) jdbc.update("DELETE FROM dataset_facet WHERE facet_id = ?", id);
        Integer n = jdbc.queryForObject("SELECT COUNT(*) FROM dataset_facet WHERE facet_id = ?", Integer.class, id);
        if (n != null && n > 0) return;
        jdbc.update("""
                INSERT INTO dataset_facet (facet_id, axis, facet_value, target_type, dataset_id, col_name, confidence,
                                           source, evidence, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""", id, axis, cut(value, 300), target, ds, col, conf, source,
                cut(evidence, 1000), now);
    }

    private static int num(Object o) {
        return o == null ? 0 : ((Number) o).intValue();
    }

    private static String cut(String s, int n) {
        return s == null || s.length() <= n ? s : s.substring(0, n);
    }
}
