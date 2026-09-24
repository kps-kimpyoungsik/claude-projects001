package com.aegis.pm.dds;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.aegis.pm.common.Rows;

/**
 * USS U5-min — "자동화가 오르는가 · 믿을 만한가"를 <b>주장이 아니라 수치</b>로 (뼈대 §7).
 *
 * <pre>
 *   coverage  = 바인딩된 컬럼 / 전체 컬럼
 *   auto_rate = 자동 판정이 그대로 서 있는 바인딩(확인 포함) / 전체 바인딩
 *   precision = 자동 판정이 사람 판정과 같았던 라벨 / 채점 라벨   (라벨 = binding_label.agree NOT NULL)
 * </pre>
 *
 * <p>precision 은 {@link BindingEngine} 이 사람 판정 <b>직전</b>에 남긴 예측으로만 계산한다 —
 * 학습 이후 엔진을 다시 돌려 채점하면 외운 답을 맞힌 점수가 되기 때문이다.
 *
 * <p>ask_count(뼈대 §7.2 4번째 숫자)는 질의 루프(U6)가 없어 아직 셀 대상이 없다.
 */
@Service
public class MetricService {

    /** 이보다 라벨이 적으면 precision 변화를 회귀로 판정하지 않는다 — 뼈대 §7.1 도메인당 최소 50건 */
    static final int MIN_LABELS = 50;
    /** 직전 스냅샷 대비 이만큼 떨어지면 회귀 (뼈대 §7.2) */
    static final double REGRESSION_DROP = 0.05;

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final JdbcTemplate jdbc;

    public MetricService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** 지금 값 — 전체(ALL) + 표준별 */
    public List<Map<String, Object>> current() {
        List<Map<String, Object>> out = new ArrayList<>();
        out.add(measure("ALL"));
        for (String std : jdbc.queryForList("SELECT DISTINCT std_id FROM dataset_binding ORDER BY std_id", String.class)) {
            out.add(measure(std));
        }
        return out;
    }

    Map<String, Object> measure(String scope) {
        boolean all = "ALL".equals(scope);
        Integer cols = all
                ? jdbc.queryForObject("SELECT COUNT(*) FROM dataset_column", Integer.class)
                : jdbc.queryForObject("""
                        SELECT COUNT(*) FROM dataset_column c JOIN dataset d ON d.dataset_id = c.dataset_id
                         WHERE d.std_id = ?""", Integer.class, scope);
        String bWhere = all ? "" : " WHERE std_id = ?";
        Object[] bArgs = all ? new Object[0] : new Object[] { scope };
        Integer bound = jdbc.queryForObject("SELECT COUNT(*) FROM dataset_binding" + bWhere, Integer.class, bArgs);
        // 자동 판정이 그대로 서 있는 바인딩 — 사람이 [맞음]으로 확인만 한 것도 포함한다.
        // 확인하면 source 가 human 으로 바뀌므로 source 만 보면 검증할수록 auto_rate 가 떨어진다.
        Integer autoN = jdbc.queryForObject("SELECT COUNT(*) FROM dataset_binding b"
                + (all ? " WHERE" : bWhere + " AND") + """
                 (b.source <> 'human' OR EXISTS (SELECT 1 FROM binding_label l
                   WHERE l.dataset_id = b.dataset_id AND l.col_name = b.col_name AND l.agree = TRUE
                     AND l.auto_std = b.std_id AND l.auto_field = b.field_key))""", Integer.class, bArgs);
        // 표준별 precision 은 "엔진이 이 표준이라고 한 것 중 맞은 비율" — auto_std 로 거른다.
        // human_std 로 거르면 recall 이 되어, 엉뚱한 표준으로 잘못 묶은 회귀가 원인 표준에 안 잡힌다.
        String lWhere = all ? " WHERE agree IS NOT NULL" : " WHERE agree IS NOT NULL AND auto_std = ?";
        Integer labels = jdbc.queryForObject("SELECT COUNT(*) FROM binding_label" + lWhere, Integer.class, bArgs);
        Integer agreed = jdbc.queryForObject("SELECT COUNT(*) FROM binding_label" + lWhere + " AND agree = TRUE",
                Integer.class, bArgs);

        Map<String, Object> m = new LinkedHashMap<>();
        m.put("scope", scope);
        // 표준별 coverage 는 그 표준으로 판정된 데이터셋의 컬럼 기준 — 사람이 다른 표준으로 고친
        // 컬럼이 섞이면 1 을 넘을 수 있어 1 로 자른다
        m.put("coverage", ratio(bound, cols));
        m.put("auto_rate", ratio(autoN, bound));
        m.put("precision", labels == null || labels == 0 ? null : ratio(agreed, labels));
        m.put("labels", labels);
        m.put("reliable", labels != null && labels >= MIN_LABELS);
        return m;
    }

    /**
     * 스냅샷을 남기고 직전 스냅샷과 비교한다. 표준·사전을 바꾼 뒤 과거가 망가졌는지 여기서 잡는다.
     * 양쪽 모두 라벨이 {@link #MIN_LABELS} 이상일 때만 회귀를 판정한다 — 표본 몇 건의 흔들림을
     * 사고로 오보하지 않는다.
     */
    @Transactional
    public Map<String, Object> snapshot() {
        String now = LocalDateTime.now().format(TS);
        List<Map<String, Object>> rows = current();
        List<Map<String, Object>> regressions = new ArrayList<>();
        for (Map<String, Object> m : rows) {
            String scope = (String) m.get("scope");
            List<Map<String, Object>> prev = Rows.lower(jdbc.queryForList("""
                    SELECT precision_v, labels, measured_at FROM struct_metric
                     WHERE scope = ? ORDER BY metric_id DESC LIMIT 1""", scope));
            jdbc.update("""
                    INSERT INTO struct_metric (measured_at, scope, coverage, auto_rate, precision_v, labels)
                    VALUES (?,?,?,?,?,?)""", now, scope, m.get("coverage"), m.get("auto_rate"),
                    m.get("precision"), m.get("labels"));
            if (prev.isEmpty()) continue;
            Map<String, Object> p = prev.get(0);
            Double before = p.get("precision_v") == null ? null : ((Number) p.get("precision_v")).doubleValue();
            Double after = (Double) m.get("precision");
            int beforeN = p.get("labels") == null ? 0 : ((Number) p.get("labels")).intValue();
            if (before != null && after != null && beforeN >= MIN_LABELS && (Integer) m.get("labels") >= MIN_LABELS
                    && before - after >= REGRESSION_DROP) {
                Map<String, Object> r = new LinkedHashMap<>();
                r.put("scope", scope);
                r.put("before", before);
                r.put("after", after);
                r.put("since", p.get("measured_at"));
                regressions.add(r);
            }
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ok", true);
        out.put("measuredAt", now);
        out.put("metrics", rows);
        out.put("regressions", regressions);
        return out;
    }

    public List<Map<String, Object>> history(String scope) {
        return Rows.lower(jdbc.queryForList("""
                SELECT measured_at, scope, coverage, auto_rate, precision_v AS precision, labels
                  FROM struct_metric WHERE scope = ? ORDER BY metric_id""", scope == null ? "ALL" : scope));
    }

    private static Double ratio(Integer num, Integer den) {
        if (num == null || den == null || den == 0) return null;
        return Math.min(1.0, (double) num / den);
    }
}
