package com.aegis.pm.engine;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import com.aegis.pm.common.Rows;
import com.aegis.pm.dataset.DatasetWriter;

/**
 * 범용 규칙 발견 엔진 — 자료가 무엇이든 <b>값의 통계</b>로 구조를 판단하고(profile), 목록으로 내고(inventory),
 * 정제 단계를 구성한다(plan·apply). 도메인별 프로그램을 새로 짜지 않는다.
 *
 * <p>학습: 사람이 고친 컬럼 역할(dataset_facet source=human)이 RoleModel 의 라벨이 된다 — 교정이 쌓일수록
 * 사전 규칙보다 자료에서 배운 판단이 앞선다.
 */
@Service
public class EngineService {

    private final JdbcTemplate jdbc;
    private final DatasetWriter datasets;

    public EngineService(JdbcTemplate jdbc, DatasetWriter datasets) {
        this.jdbc = jdbc;
        this.datasets = datasets;
    }

    /** 사람 라벨 → 학습 데이터. 라벨 컬럼의 현재 값으로 특징을 다시 계산한다 */
    public RoleModel model() {
        List<RoleModel.Label> labels = new ArrayList<>();
        Map<String, List<Map<String, String>>> cache = new HashMap<>();
        for (Map<String, Object> f : Rows.lower(jdbc.queryForList(
                "SELECT dataset_id, col_name, facet_value FROM dataset_facet WHERE axis = 'role' AND source = 'human'"))) {
            String ds = (String) f.get("dataset_id");
            List<Map<String, String>> rows = cache.computeIfAbsent(ds, k -> datasets.rows(k, 0));
            DataProfiler.Profile p = DataProfiler.profile(RefinePlanner.column(rows, (String) f.get("col_name")));
            if (p.filled() > 0) labels.add(new RoleModel.Label(p.vector(), (String) f.get("facet_value")));
        }
        return new RoleModel(labels);
    }

    public List<String> headers(String datasetId) {
        return jdbc.queryForList("SELECT name FROM dataset_column WHERE dataset_id = ? ORDER BY col_no", String.class, datasetId);
    }

    /** 데이터셋 1개 — 컬럼마다 특징·역할, 헤더 의심, 정제 계획 */
    public Map<String, Object> profile(String datasetId) {
        return profile(datasetId, model());
    }

    Map<String, Object> profile(String datasetId, RoleModel model) {
        List<String> headers = headers(datasetId);
        List<Map<String, String>> rows = datasets.rows(datasetId, 0);
        List<Map<String, Object>> cols = new ArrayList<>();
        Map<String, String> roles = new LinkedHashMap<>();
        int echo = 0, typedHeader = 0, generated = 0;
        for (String h : headers) {
            List<String> col = RefinePlanner.column(rows, h);
            DataProfiler.Profile p = DataProfiler.profile(col);
            RoleModel.Guess g = model.guess(p);
            roles.put(h, g.role());
            // 헤더가 데이터처럼 보이는가 — 헤더 값이 그 열에 또 나오거나, 헤더 자체가 숫자·날짜
            if (col.contains(h)) echo++;
            char k = DataProfiler.kind(h);
            if (k == 'N' || k == 'D') typedHeader++;
            if (h.matches("col\\d+")) generated++;
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("name", h);
            m.put("role", g.role());
            m.put("confidence", g.confidence());
            m.put("evidence", g.evidence());
            m.put("fill", r2(p.fill()));
            m.put("distinctRatio", r2(p.distinctRatio()));
            m.put("numericRatio", r2(p.numericRatio()));
            m.put("dateRatio", r2(p.dateRatio()));
            m.put("entropy", r2(p.entropy()));
            m.put("avgLen", r2(p.avgLen()));
            cols.add(m);
        }
        int n = Math.max(1, headers.size());
        boolean suspect = echo >= 2 || (double) typedHeader / n >= 0.3;
        List<RefinePlanner.Op> ops = RefinePlanner.plan(headers, rows, roles);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("datasetId", datasetId);
        out.put("rows", rows.size());
        out.put("columns", cols);
        out.put("headerSuspect", suspect);
        out.put("headerEvidence", "헤더 반향 " + echo + " · 숫자·날짜 헤더 " + typedHeader + " · 자동 이름 " + generated);
        out.put("refine", ops);
        out.put("labels", model.labelCount());
        return out;
    }

    /** 자료 리스트업 — 전 데이터셋의 구조·역할 분포·품질 문제·정제 제안 요약 */
    public List<Map<String, Object>> inventory() {
        RoleModel model = model();
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> d : Rows.lower(jdbc.queryForList("""
                SELECT d.dataset_id, d.name, d.sheet_name, d.row_count, d.col_count, q.verdict, q.score
                  FROM dataset d LEFT JOIN dataset_qualification q ON q.dataset_id = d.dataset_id
                 ORDER BY d.created_at, d.dataset_id"""))) {
            String id = (String) d.get("dataset_id");
            Map<String, Object> p = profile(id, model);
            Map<String, Integer> roleCount = new LinkedHashMap<>();
            for (Object c : (List<?>) p.get("columns")) roleCount.merge((String) ((Map<?, ?>) c).get("role"), 1, Integer::sum);
            Map<String, Integer> opCount = new LinkedHashMap<>();
            int fixable = 0;
            for (Object o : (List<?>) p.get("refine")) {
                RefinePlanner.Op op = (RefinePlanner.Op) o;
                opCount.merge(op.op(), op.cells(), Integer::sum);
                if (op.applies()) fixable += op.cells();
            }
            Map<String, Object> row = new LinkedHashMap<>(d);
            row.put("roles", roleCount);
            row.put("headerSuspect", p.get("headerSuspect"));
            row.put("refine", opCount);
            row.put("fixableCells", fixable);
            out.add(row);
        }
        return out;
    }

    /** 정제 적용 — 원본은 그대로 두고 "{이름} (정제)" 새 데이터셋을 만든다. 적재 파이프라인(바인딩·패싯·판정)이 이어서 돈다 */
    public Map<String, Object> apply(String datasetId) {
        Map<String, Object> d = Rows.lower(jdbc.queryForMap("SELECT * FROM dataset WHERE dataset_id = ?", datasetId));
        List<String> headers = headers(datasetId);
        List<Map<String, String>> rows = datasets.rows(datasetId, 0);
        @SuppressWarnings("unchecked")
        List<RefinePlanner.Op> ops = (List<RefinePlanner.Op>) profile(datasetId).get("refine");
        Map<String, Object> refined = RefinePlanner.apply(headers, rows, ops);
        String newId = datasetId + "-R";
        @SuppressWarnings("unchecked")
        List<String> h2 = (List<String>) refined.get("headers");
        @SuppressWarnings("unchecked")
        List<Map<String, String>> r2 = (List<Map<String, String>>) refined.get("rows");
        datasets.write(newId, d.get("name") + " (정제)", (String) d.get("sheet_name"), (String) d.get("source_file"),
                (String) d.get("batch_id"), h2, r2);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ok", true);
        out.put("source", datasetId);
        out.put("refined", newId);
        out.put("rows", rows.size() + " → " + r2.size());
        out.put("columns", headers.size() + " → " + h2.size());
        out.put("applied", ops.stream().filter(RefinePlanner.Op::applies).map(o -> o.op() + (o.column() == null ? "" : ":" + o.column())).toList());
        return out;
    }

    private static double r2(double v) {
        return Math.round(v * 100) / 100.0;
    }
}
