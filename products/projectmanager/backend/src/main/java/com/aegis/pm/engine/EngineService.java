package com.aegis.pm.engine;

import java.io.FileInputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import com.aegis.pm.common.Rows;
import com.aegis.pm.dataset.DatasetIngestService;
import com.aegis.pm.dataset.DatasetWriter;
import com.aegis.pm.pii.PiiVault;

/**
 * 범용 규칙 발견 엔진 — 자료가 무엇이든 <b>값의 통계</b>로 구조를 판단하고(profile), 목록으로 내고(inventory),
 * 정제 단계를 구성한다(plan·apply). 도메인별 프로그램을 새로 짜지 않는다.
 *
 * <p>학습: 사람이 고친 컬럼 역할(dataset_facet source=human)이 RoleModel 의 라벨이 된다 — 교정이 쌓일수록
 * 사전 규칙보다 자료에서 배운 판단이 앞선다.
 *
 * <p>자료 보존(plans/_opens/data_lineage_review): 정제본 = f(원본, 계획, 사람 결정). 사라지거나 바뀐 값은 전부
 * refine_trace 에 남고, 사람이 복원(결정)하거나 원본 칸을 직접 고치면 정제본을 다시 만든다. 비슷한 양식끼리는
 * 자동으로 묶어(분류) 묶음 전체 자료로 역할을 판단한다 — 자료를 더 올릴수록 판단이 안정된다.
 */
@Service
public class EngineService {

    /** 컬럼 이름 집합의 자카드 유사도가 이 이상이면 같은 묶음 */
    static final double GROUP_SIMILARITY = 0.5;

    private final JdbcTemplate jdbc;
    private final DatasetWriter datasets;
    private final TraceStore traces;
    private final DatasetIngestService ingest;
    private final PiiVault pii;

    public EngineService(JdbcTemplate jdbc, DatasetWriter datasets, TraceStore traces, DatasetIngestService ingest, PiiVault pii) {
        this.jdbc = jdbc;
        this.datasets = datasets;
        this.traces = traces;
        this.ingest = ingest;
        this.pii = pii;
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
        return profile(datasetId, model(), groupOf(), new HashMap<>());
    }

    /**
     * 역할은 <b>묶음 전체 행</b>으로 판단한다(같은 이름 컬럼의 값을 합친다) — 한 파일 10행으로 애매한 열도 여러 파일을
     * 합치면 분명해진다. 묶음이 자기 하나뿐이면 자기 행만 본다.
     */
    Map<String, Object> profile(String datasetId, RoleModel model, Map<String, List<String>> groups,
                                Map<String, List<Map<String, String>>> cache) {
        List<String> headers = headers(datasetId);
        List<Map<String, String>> rows = cache.computeIfAbsent(datasetId, k -> datasets.rows(k, 0));
        List<String> members = groups.getOrDefault(datasetId, List.of(datasetId));
        List<Map<String, Object>> cols = new ArrayList<>();
        Map<String, String> roles = new LinkedHashMap<>();
        int echo = 0, typedHeader = 0, generated = 0;
        for (String h : headers) {
            List<String> col = RefinePlanner.column(rows, h);
            List<String> pooled = members.size() < 2 ? col : pooled(members, h, cache);
            DataProfiler.Profile p = DataProfiler.profile(pooled);
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
            m.put("evidence", g.evidence() + (pooled.size() > col.size() ? " · 묶음 " + pooled.size() + "행" : ""));
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
        out.put("roles", roles);
        out.put("group", members);
        out.put("headerSuspect", suspect);
        out.put("headerEvidence", "헤더 반향 " + echo + " · 숫자·날짜 헤더 " + typedHeader + " · 자동 이름 " + generated);
        out.put("refine", ops);
        out.put("labels", model.labelCount());
        return out;
    }

    private List<String> pooled(List<String> members, String col, Map<String, List<Map<String, String>>> cache) {
        List<String> out = new ArrayList<>();
        for (String m : members) {
            List<Map<String, String>> rs = cache.computeIfAbsent(m, k -> datasets.rows(k, 0));
            if (!rs.isEmpty() && headers(m).contains(col)) out.addAll(RefinePlanner.column(rs, col));
        }
        return out;
    }

    /** 자료 리스트업 — 전 데이터셋의 구조·역할 분포·품질 문제·정제 제안·이력 건수 요약 */
    public List<Map<String, Object>> inventory() {
        RoleModel model = model();
        Map<String, List<String>> groups = groupOf();
        Map<String, List<Map<String, String>>> cache = new HashMap<>();
        Map<String, Integer> traceCount = new HashMap<>();
        for (Map<String, Object> t : Rows.lower(jdbc.queryForList("SELECT dataset_id, COUNT(*) AS n FROM refine_trace GROUP BY dataset_id"))) {
            traceCount.put((String) t.get("dataset_id"), ((Number) t.get("n")).intValue());
        }
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> d : Rows.lower(jdbc.queryForList("""
                SELECT d.dataset_id, d.name, d.sheet_name, d.row_count, d.col_count, q.verdict, q.score
                  FROM dataset d LEFT JOIN dataset_qualification q ON q.dataset_id = d.dataset_id
                 ORDER BY d.created_at, d.dataset_id"""))) {
            String id = (String) d.get("dataset_id");
            Map<String, Object> p = profile(id, model, groups, cache);
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
            row.put("traces", traceCount.getOrDefault(id, 0));
            row.put("group", ((List<?>) p.get("group")).get(0));
            out.add(row);
        }
        return out;
    }

    // ── 정제 · 결정 · 직접 수정 ────────────────────────────────────────────

    static String sourceOf(String datasetId) {
        return datasetId.endsWith("-R") ? datasetId.substring(0, datasetId.length() - 2) : datasetId;
    }

    /**
     * 정제 적용 — 원본은 그대로 두고 "{이름} (정제)" 새 데이터셋을 만든다. 사람 결정(복원)은 적용하지 않고,
     * 사라지거나 바뀐 값은 전부 정제본의 이력으로 남긴다. 적재 파이프라인(바인딩·패싯·판정)이 이어서 돈다.
     */
    public Map<String, Object> apply(String datasetId) {
        String src = sourceOf(datasetId);
        Map<String, Object> d = Rows.lower(jdbc.queryForMap("SELECT * FROM dataset WHERE dataset_id = ?", src));
        List<String> headers = headers(src);
        List<Map<String, String>> rows = datasets.rows(src, 0);
        @SuppressWarnings("unchecked")
        List<RefinePlanner.Op> ops = (List<RefinePlanner.Op>) profile(src).get("refine");
        Map<String, Object> refined = RefinePlanner.apply(headers, rows, ops, traces.keeper(src));
        String newId = src + "-R";
        @SuppressWarnings("unchecked")
        List<String> h2 = (List<String>) refined.get("headers");
        @SuppressWarnings("unchecked")
        List<Map<String, String>> r2 = (List<Map<String, String>>) refined.get("rows");
        @SuppressWarnings("unchecked")
        List<TraceStore.Trace> lost = (List<TraceStore.Trace>) refined.get("traces");
        datasets.write(newId, d.get("name") + " (정제)", (String) d.get("sheet_name"), (String) d.get("source_file"),
                (String) d.get("batch_id"), h2, r2);
        traces.add(newId, src, lost);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ok", true);
        out.put("source", src);
        out.put("refined", newId);
        out.put("rows", rows.size() + " → " + r2.size());
        out.put("columns", headers.size() + " → " + h2.size());
        out.put("traced", lost.size());
        out.put("applied", ops.stream().filter(RefinePlanner.Op::applies).map(o -> o.op() + (o.column() == null ? "" : ":" + o.column())).toList());
        return out;
    }

    /** 이력 + 사람 결정 — 정제본이든 원본이든 그 데이터셋에 쌓인 것 */
    public Map<String, Object> traces(String datasetId) {
        Map<String, Object> out = new LinkedHashMap<>();
        List<Map<String, Object>> list = new ArrayList<>(traces.list(datasetId));
        if (!sourceOf(datasetId).equals(datasetId))   // 정제본에서 보면 원본의 직접 수정도 함께 — 수정은 원본에 남는다
            for (Map<String, Object> t : traces.list(sourceOf(datasetId))) if ("EDIT".equals(t.get("stage"))) list.add(t);
        Map<String, Integer> byOp = new LinkedHashMap<>();
        for (Map<String, Object> t : list) byOp.merge(t.get("stage") + ":" + t.get("op"), 1, Integer::sum);
        out.put("datasetId", datasetId);
        out.put("source", sourceOf(datasetId));
        out.put("summary", byOp);
        out.put("traces", list);
        out.put("decisions", traces.decisions(sourceOf(datasetId)));
        return out;
    }

    /** 복원 — 그 정제를 하지 않도록 결정하고 정제본을 다시 만든다. col=null 모든 열, row=-1 모든 행 */
    public Map<String, Object> restore(String datasetId, String op, String col, int row) {
        traces.keep(sourceOf(datasetId), op, col, row);
        return apply(datasetId);
    }

    /** 복원 취소 — 결정을 지우고 정제본을 다시 만든다 */
    public Map<String, Object> unrestore(String datasetId, String op, String col, int row) {
        traces.unkeep(sourceOf(datasetId), op, col, row);
        return apply(datasetId);
    }

    /**
     * 직접 수정 — <b>원본</b> 칸을 고치고 이전·이후 값을 EDIT 이력으로 남긴다. 정제본이 있으면 다시 만든다
     * (정제본을 직접 고치면 다음 정제 때 사라진다). 되돌리기 = 이력의 이전 값으로 다시 수정.
     */
    public Map<String, Object> edit(String datasetId, int rowNo, String col, String value) {
        String src = sourceOf(datasetId);
        if (!headers(src).contains(col)) throw new IllegalArgumentException("없는 컬럼: " + col);
        List<Map<String, String>> rows = datasets.rows(src, 0);
        if (rowNo < 0 || rowNo >= rows.size()) throw new IllegalArgumentException("행 범위 밖: " + rowNo);
        String before = rows.get(rowNo).get(col);
        datasets.updateCell(src, rowNo, Map.of(col, value == null ? "" : value));
        String after = datasets.rows(src, 0).get(rowNo).get(col);   // 개인정보 칸은 토큰으로 저장된다 — 저장된 그대로 기록
        traces.add(src, src, List.of(new TraceStore.Trace("EDIT", "MANUAL_EDIT", rowNo, col, before, after)));
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ok", true);
        out.put("source", src);
        out.put("before", before);
        out.put("after", after);
        if (datasets.exists(src + "-R")) out.put("refine", apply(src));
        return out;
    }

    // ── 동적 분류(묶음) · 재검증 ──────────────────────────────────────────

    /**
     * 컬럼 이름 집합이 비슷한 데이터셋끼리 묶는다(union-find). 묶음 수는 자료가 정한다 — 같은 양식을 매주 올리면
     * 한 묶음에 모인다. 정제본(-R)은 원본과 겹치므로 뺀다.
     */
    // ponytail: 전 쌍 비교 O(n²) — 데이터셋 수천 개면 MinHash 로 후보만 좁힐 것
    public Map<String, List<String>> groupOf() {
        List<String> ids = jdbc.queryForList("SELECT dataset_id FROM dataset ORDER BY created_at, dataset_id", String.class)
                .stream().filter(i -> !i.endsWith("-R")).toList();
        Map<String, Set<String>> cols = new HashMap<>();
        for (String i : ids) {
            Set<String> s = new HashSet<>();
            // 자동 이름(col1…)은 헤더 없는 표면 전부 같다 — 같다고 묶을 근거가 아니다
            for (String h : headers(i)) if (!h.matches("col\\d+")) s.add(h.trim().toLowerCase());
            cols.put(i, s);
        }
        int[] parent = new int[ids.size()];
        for (int i = 0; i < parent.length; i++) parent[i] = i;
        for (int i = 0; i < ids.size(); i++)
            for (int j = i + 1; j < ids.size(); j++)
                if (jaccard(cols.get(ids.get(i)), cols.get(ids.get(j))) >= GROUP_SIMILARITY) parent[find(parent, j)] = find(parent, i);
        Map<Integer, List<String>> byRoot = new LinkedHashMap<>();
        for (int i = 0; i < ids.size(); i++) byRoot.computeIfAbsent(find(parent, i), k -> new ArrayList<>()).add(ids.get(i));
        Map<String, List<String>> out = new HashMap<>();
        for (List<String> g : byRoot.values()) for (String i : g) out.put(i, g);
        for (String i : jdbc.queryForList("SELECT dataset_id FROM dataset", String.class))   // 정제본은 원본의 묶음을 따른다
            if (i.endsWith("-R")) out.put(i, out.getOrDefault(sourceOf(i), List.of(i)));
        return out;
    }

    public List<Map<String, Object>> groups() {
        Map<String, List<String>> g = groupOf();
        Map<String, Map<String, Object>> out = new LinkedHashMap<>();
        for (List<String> members : new LinkedHashSet<>(g.values())) {
            String key = members.get(0);
            if (out.containsKey(key) || key.endsWith("-R")) continue;
            Set<String> shared = null;
            List<Map<String, Object>> ms = new ArrayList<>();
            for (String m : members) {
                List<String> h = headers(m);
                shared = shared == null ? new LinkedHashSet<>(h) : shared;
                shared.retainAll(h);
                Map<String, Object> d = Rows.lower(jdbc.queryForMap("SELECT dataset_id, name, row_count FROM dataset WHERE dataset_id = ?", m));
                ms.add(d);
            }
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("group", key);
            row.put("size", members.size());
            row.put("rows", ms.stream().mapToInt(d -> ((Number) d.get("row_count")).intValue()).sum());
            row.put("sharedColumns", shared);
            row.put("members", ms);
            out.put(key, row);
        }
        return new ArrayList<>(out.values());
    }

    /**
     * 묶음 재검증 — 데이터셋마다 "자기 행만 본 역할"과 "묶음 전체로 본 역할"을 비교하고 정제 계획을 다시 세운다.
     * 자료를 더 올린 뒤 부르면 표본이 늘어 판단이 달라진 컬럼이 드러난다.
     */
    public Map<String, Object> reverify(String groupKey) {
        Map<String, List<String>> groups = groupOf();
        List<String> members = groups.get(groupKey);
        if (members == null) throw new IllegalArgumentException("없는 묶음: " + groupKey);
        RoleModel model = model();
        Map<String, List<Map<String, String>>> cache = new HashMap<>();
        List<Map<String, Object>> result = new ArrayList<>();
        int changed = 0;
        for (String m : members) {
            @SuppressWarnings("unchecked")
            Map<String, String> solo = (Map<String, String>) profile(m, model, Map.of(), cache).get("roles");
            Map<String, Object> p = profile(m, model, groups, cache);
            @SuppressWarnings("unchecked")
            Map<String, String> pooled = (Map<String, String>) p.get("roles");
            List<String> diffs = new ArrayList<>();
            solo.forEach((c, r) -> { if (!r.equals(pooled.get(c))) diffs.add(c + ": " + r + " → " + pooled.get(c)); });
            changed += diffs.size();
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("datasetId", m);
            row.put("rows", p.get("rows"));
            row.put("roleChanges", diffs);
            row.put("refine", p.get("refine"));
            result.add(row);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("group", groupKey);
        out.put("members", members.size());
        out.put("roleChanges", changed);
        out.put("datasets", result);
        return out;
    }

    // ── 헤더 다시 지정 (봉인 원본에서 재적재) ────────────────────────────

    /**
     * 봉인 원본을 개인키로 임시 파일에 풀어, 헤더 행을 지정해(0부터, -1=헤더 없음, null=자동) 같은 ID로 다시 적재한다.
     * 임시 평문은 끝나면 바로 지운다. 이전 표는 교체되고, 헤더 위로 밀린 행은 새 이력에 남는다.
     */
    public Map<String, Object> reingest(String datasetId, Integer headerRow) throws Exception {
        Map<String, Object> d = Rows.lower(jdbc.queryForMap("SELECT * FROM dataset WHERE dataset_id = ?", datasetId));
        List<String> stored = jdbc.queryForList("SELECT stored_path FROM upload_batch WHERE batch_id = ?", String.class, d.get("batch_id"));
        if (stored.isEmpty() || stored.get(0) == null) throw new IllegalStateException("원본 파일 기록이 없습니다 (배치 " + d.get("batch_id") + ")");
        Path src = Path.of(stored.get(0));
        if (!Files.exists(src)) throw new IllegalStateException("원본 파일이 없습니다: " + src.getFileName());
        Path tmp = null;
        try {
            Path file = src;
            if (src.toString().endsWith(".sealed")) {
                tmp = Files.createTempFile("pm-reingest-", ".xlsx");
                file = pii.openStored(src, tmp);
            }
            int before = ((Number) d.get("row_count")).intValue(), n;
            try (FileInputStream in = new FileInputStream(file.toFile()); Workbook wb = new XSSFWorkbook(in)) {
                Sheet sheet = wb.getSheet((String) d.get("sheet_name"));
                if (sheet == null) throw new IllegalStateException("원본에 시트가 없습니다: " + d.get("sheet_name"));
                n = ingest.ingestSheet(datasetId, (String) d.get("name"), sheet, (String) d.get("source_file"), (String) d.get("batch_id"), headerRow);
            }
            if (n == 0) throw new IllegalStateException("지정한 헤더로는 표를 읽을 수 없습니다 — 기존 표를 그대로 둡니다");
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("ok", true);
            out.put("datasetId", datasetId);
            out.put("headerRow", headerRow == null ? "자동" : headerRow < 0 ? "없음" : String.valueOf(headerRow + 1));
            out.put("rows", before + " → " + n);
            out.put("columns", headers(datasetId));
            return out;
        } finally {
            if (tmp != null) Files.deleteIfExists(tmp);
        }
    }

    private static int find(int[] p, int i) {
        while (p[i] != i) i = p[i] = p[p[i]];
        return i;
    }

    static double jaccard(Set<String> a, Set<String> b) {
        if (a.isEmpty() && b.isEmpty()) return 0;
        Set<String> u = new HashSet<>(a);
        u.addAll(b);
        int inter = 0;
        for (String x : a) if (b.contains(x)) inter++;
        return (double) inter / u.size();
    }

    private static double r2(double v) {
        return Math.round(v * 100) / 100.0;
    }
}
