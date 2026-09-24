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
    /** 엑셀 일련번호로 볼 수 있는 범위 — 1954-10 ~ 2119-01 */
    static final double SERIAL_MIN = 20000, SERIAL_MAX = 80000;

    private final JdbcTemplate jdbc;
    private final com.aegis.pm.pii.PiiVault pii;
    private final com.aegis.pm.engine.EngineService engine;
    private final com.aegis.pm.dataset.DatasetWriter writer;

    public FacetService(JdbcTemplate jdbc, com.aegis.pm.pii.PiiVault pii, com.aegis.pm.engine.EngineService engine,
                        com.aegis.pm.dataset.DatasetWriter writer) {
        this.jdbc = jdbc;
        this.pii = pii;
        this.engine = engine;
        this.writer = writer;
    }

    private List<Map<String, String>> datasetRows(String datasetId) {
        return writer.rows(datasetId, 0);
    }

    /** 시간 열의 최댓값 — 엑셀 일련번호·여러 날짜 표기를 yyyy-MM-dd 로 맞춘 뒤 비교 */
    static String maxDate(List<String> values) {
        String best = null;
        for (String v : values) {
            if (v == null || v.isBlank()) continue;
            String d = asDate(v.trim());
            java.util.regex.Matcher m = java.util.regex.Pattern.compile("^(\\d{4})[-./](\\d{1,2})[-./](\\d{1,2})").matcher(d);
            if (!m.find()) continue;
            String iso = String.format("%s-%02d-%02d", m.group(1), Integer.parseInt(m.group(2)), Integer.parseInt(m.group(3)));
            if (best == null || iso.compareTo(best) > 0) best = iso;
        }
        return best;
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

        // role — 컬럼마다. 컬럼명·도메인 단어가 아니라 **값의 통계**로 엔진이 판정한다(EngineService·RoleModel).
        // 사람이 고친 라벨이 쌓이면 kNN 이 사전 규칙을 이긴다. 예외 하나: 개인정보 분류기가 성명 칸으로 본 컬럼은
        // person — 이것은 역할 추정이 아니라 보호 규칙이다(가명 토큰이 없는 비활성 환경에서도 같은 판정이 나오게).
        Map<String, Integer> roles = new LinkedHashMap<>();
        String baseDate = null;
        List<Map<String, String>> rows = engine == null ? List.of() : datasetRows(datasetId);
        com.aegis.pm.engine.RoleModel model = engine.model();
        for (String col : jdbc.queryForList("SELECT name FROM dataset_column WHERE dataset_id = ? ORDER BY col_no", String.class, datasetId)) {
            List<String> values = new java.util.ArrayList<>(rows.size());
            for (Map<String, String> r : rows) values.add(r.get(col));
            com.aegis.pm.engine.DataProfiler.Profile p = com.aegis.pm.engine.DataProfiler.profile(values);
            if (p.filled() == 0) continue;   // 완전히 빈 열 — 표의 일부가 아니다
            com.aegis.pm.engine.RoleModel.Guess g = PiiRegistry.PERSON.equals(PiiRegistry.kindOfHeader(col))
                    ? new com.aegis.pm.engine.RoleModel.Guess("person", 0.9, "개인정보 분류기 — 성명 칸")
                    : model.guess(p);
            put(datasetId, "role", g.role(), "column", col, g.confidence(), g.evidence().startsWith("학습") ? "stat" : "rule",
                    g.evidence(), now);
            roles.merge(g.role(), 1, Integer::sum);
            if ("time".equals(g.role())) {
                String mx = maxDate(values);
                if (mx != null && (baseDate == null || mx.compareTo(baseDate) > 0)) baseDate = mx;
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
