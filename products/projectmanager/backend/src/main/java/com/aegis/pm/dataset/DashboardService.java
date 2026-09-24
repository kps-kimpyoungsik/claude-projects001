package com.aegis.pm.dataset;

import com.aegis.pm.common.Rows;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * 대시보드 — 화면(메뉴)의 정의가 DB에 있다.
 *
 *   kind=dataset : 데이터셋 1개짜리 기본 대시보드. 저장된 구성이 없으면 컬럼 타입으로 자동 초안을 만든다.
 *   kind=custom  : 사용자가 만든 대시보드. 위젯마다 데이터셋을 골라 여러 개를 한 화면에 섞는다.
 *
 * 위젯은 예외 없이 대시보드에 속하고, 집계는 서버가 계산해 그릴 수 있는 형태로 내려준다.
 *
 * <p><b>위젯 = 무엇을(지표) × 어떻게(뷰)</b> — 두 축이 따로다. 지표는 (집계 × 대상 컬럼 × 분류 트리),
 * 뷰는 (kpi·pie·bar·progress·trend·list·box·group·table). 그래서 서버 응답 모양은 뷰와 무관하게
 * 하나이고({@code total/percent/items}), 화면은 그중 필요한 것만 골라 그린다.
 */
@Service
public class DashboardService {

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final DateTimeFormatter ID_TS = DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss");
    /** 분포 차트에 그릴 기본 항목 수 (나머지는 기타로 묶는다) */
    private static final int TOP_N = 8;
    /** 표 위젯 미리보기 행 수 */
    private static final int TABLE_ROWS = 50;
    /** 위젯 집계가 전 행을 메모리에 올린다 — 이 수를 넘으면 그 위젯만 오류로 표시하고 나머지는 그린다 */
    private static final int MAX_AGGREGATE_ROWS = 50_000;
    /** 뷰별 기본 크기 — 폭(1~12칸) × 높이(행) */
    private static final Map<String, int[]> DEFAULT_SPAN = Map.of(
            "kpi", new int[]{3, 1}, "progress", new int[]{4, 1}, "pie", new int[]{4, 2},
            "donut", new int[]{4, 2}, "bar", new int[]{6, 2}, "trend", new int[]{8, 2},
            "list", new int[]{4, 2}, "box", new int[]{6, 2}, "group", new int[]{6, 3});
    /** 분류 트리를 쓰는 뷰 — 옛 구성에서 col 이 분류 컬럼이었던 것들 */
    private static final List<String> GROUP_VIEWS =
            List.of("bar", "donut", "pie", "trend", "list", "box", "group");

    private final JdbcTemplate jdbc;
    private final DatasetWriter datasets;
    private final ObjectMapper json = new ObjectMapper();

    public DashboardService(JdbcTemplate jdbc, DatasetWriter datasets) {
        this.jdbc = jdbc;
        this.datasets = datasets;
    }

    // ── 데이터셋 ────────────────────────────────────────────────────────────

    public List<Map<String, Object>> datasets() {
        return datasets(false);
    }

    /**
     * 목록 — 자격 판정(CQG)을 함께 싣는다. 격리(REJECTED)된 표는 기본으로 숨긴다(삭제가 아니다, 06 §2.3).
     * 아직 평가 전인 표(verdict NULL)는 보인다 — 모르는 것을 숨기지 않는다.
     */
    public List<Map<String, Object>> datasets(boolean includeQuarantined) {
        return lower(jdbc.queryForList("""
                SELECT d.*, q.verdict, q.score, q.reason AS qualify_reason, q.quarantined, q.override_by,
                       (SELECT MAX(f.facet_value) FROM dataset_facet f WHERE f.dataset_id = d.dataset_id AND f.axis = 'domain') AS domain
                  FROM dataset d LEFT JOIN dataset_qualification q ON q.dataset_id = d.dataset_id
                """ + (includeQuarantined ? "" : " WHERE q.quarantined IS NULL OR q.quarantined = FALSE")
                + " ORDER BY d.created_at DESC, d.dataset_id DESC"));
    }

    public Map<String, Object> dataset(String id) {
        Map<String, Object> d = lower(jdbc.queryForMap("SELECT * FROM dataset WHERE dataset_id = ?", id));
        d.put("columns", columns(id));
        return d;
    }

    public List<Map<String, Object>> columns(String id) {
        return lower(jdbc.queryForList(
                "SELECT c.col_no, c.name, c.data_type, c.distinct_n, c.null_n, c.min_v, c.max_v, c.sum_v,"
                        + " (SELECT MAX(f.facet_value) FROM dataset_facet f WHERE f.dataset_id = c.dataset_id AND f.axis = 'role'"
                        + "   AND f.col_name = c.name) AS role"
                        + " FROM dataset_column c WHERE c.dataset_id = ? ORDER BY c.col_no", id));
    }

    public List<Map<String, String>> rows(String id, int limit) {
        return datasets.rows(id, limit);   // 자르는 일은 DB가 한다 — 전 행을 올린 뒤 버리지 않는다
    }

    /** 컬럼 하나의 값 목록 — 진척율의 완료로 볼 값을 화면에서 고르게 한다 */
    public List<Map<String, Object>> values(String datasetId, String col, int limit) {
        Map<String, Integer> count = new LinkedHashMap<>();
        datasets.forEachRow(datasetId, r -> count.merge(label(r.get(col)), 1, Integer::sum));
        List<Map<String, Object>> out = new ArrayList<>();
        count.forEach((k, n) -> out.add(pair("name", k, "n", n)));
        out.sort((a, b) -> num(b, "n") - num(a, "n"));
        return limit > 0 && out.size() > limit ? out.subList(0, limit) : out;
    }

    @Transactional
    public Map<String, Object> rename(String id, String name) {
        jdbc.update("UPDATE dataset SET name = ?, updated_at = ? WHERE dataset_id = ?",
                name, LocalDateTime.now().format(TS), id);
        return Map.of("ok", true, "datasetId", id, "name", name);
    }

    @Transactional
    public Map<String, Object> deleteDataset(String id) {
        // 이 데이터셋만 쓰던 대시보드는 함께 정리한다 (빈 대시보드가 메뉴에 남지 않게)
        jdbc.update("DELETE FROM dashboard_widget WHERE dataset_id = ?", id);
        jdbc.update("DELETE FROM dashboard WHERE kind = 'dataset' AND dataset_id = ?", id);
        jdbc.update("DELETE FROM dataset_row WHERE dataset_id = ?", id);
        jdbc.update("DELETE FROM dataset_column WHERE dataset_id = ?", id);
        jdbc.update("DELETE FROM dataset_facet WHERE dataset_id = ?", id);          // 고아로 남지 않게
        jdbc.update("DELETE FROM dataset_qualification WHERE dataset_id = ?", id);
        jdbc.update("DELETE FROM dataset_binding WHERE dataset_id = ?", id);
        int n = jdbc.update("DELETE FROM dataset WHERE dataset_id = ?", id);
        return n > 0 ? Map.of("ok", true, "deleted", id)
                : Map.of("ok", false, "error", "없는 데이터셋입니다: " + id);
    }

    // ── 대시보드 목록·생성 ──────────────────────────────────────────────────

    public List<Map<String, Object>> dashboards() {
        List<Map<String, Object>> list = lower(jdbc.queryForList(
                "SELECT * FROM dashboard ORDER BY pos, created_at"));
        for (Map<String, Object> d : list) {
            Integer n = jdbc.queryForObject("SELECT COUNT(*) FROM dashboard_widget WHERE dashboard_id = ?",
                    Integer.class, String.valueOf(d.get("dashboard_id")));
            d.put("widget_count", n == null ? 0 : n);
        }
        return list;
    }

    /** LNB 가 읽는 메뉴 목록 — 메뉴 정의가 코드가 아니라 DB에 있다 */
    public List<Map<String, Object>> menu() {
        return lower(jdbc.queryForList(
                "SELECT dashboard_id, name, pos FROM dashboard WHERE show_in_menu = TRUE ORDER BY pos, created_at"));
    }

    /**
     * 컬럼명 대소문자를 소문자로 통일한다.
     *
     * H2 는 따옴표 없는 식별자를 대문자로, PostgreSQL 은 소문자로 돌려준다. 그대로 JSON 으로
     * 나가면 화면이 {@code d.dataset_id} 를 못 읽어 undefined 가 된다(라우팅이 깨진 원인).
     * 화면은 소문자 하나만 보게 두고, DB 차이는 여기서 흡수한다.
     */
    /** 컬럼 키 소문자 통일 — 구현은 {@link Rows} 하나뿐이다(원천 중복 금지) */
    private static List<Map<String, Object>> lower(List<Map<String, Object>> rows) {
        return Rows.lower(rows);
    }

    private static Map<String, Object> lower(Map<String, Object> row) {
        Map<String, Object> m = new LinkedHashMap<>();
        row.forEach((k, v) -> m.put(k == null ? "" : k.toLowerCase(), v));
        return m;
    }

    @Transactional
    public Map<String, Object> createDashboard(String name, String description) {
        String id = "DB-" + LocalDateTime.now().format(ID_TS);
        String now = LocalDateTime.now().format(TS);
        Integer max = jdbc.queryForObject("SELECT COALESCE(MAX(pos), 0) FROM dashboard", Integer.class);
        jdbc.update("""
                INSERT INTO dashboard (dashboard_id, name, description, kind, dataset_id, pos,
                                       show_in_menu, created_at, updated_at)
                VALUES (?,?,?,'custom',NULL,?,TRUE,?,?)
                """, id, name, description, (max == null ? 0 : max) + 1, now, now);
        return Map.of("ok", true, "dashboardId", id, "name", name);
    }

    @Transactional
    public Map<String, Object> updateDashboard(String id, Map<String, Object> body) {
        List<String> sets = new ArrayList<>();
        List<Object> args = new ArrayList<>();
        if (body.containsKey("name")) { sets.add("name = ?"); args.add(str(body, "name")); }
        if (body.containsKey("description")) { sets.add("description = ?"); args.add(str(body, "description")); }
        if (body.containsKey("showInMenu")) { sets.add("show_in_menu = ?"); args.add(Boolean.TRUE.equals(body.get("showInMenu"))); }
        if (body.containsKey("pos")) { sets.add("pos = ?"); args.add(num(body, "pos")); }
        if (sets.isEmpty()) return Map.of("ok", false, "error", "변경할 항목이 없습니다.");
        sets.add("updated_at = ?");
        args.add(LocalDateTime.now().format(TS));
        args.add(id);
        jdbc.update("UPDATE dashboard SET " + String.join(", ", sets) + " WHERE dashboard_id = ?", args.toArray());
        return Map.of("ok", true, "dashboardId", id);
    }

    @Transactional
    public Map<String, Object> deleteDashboard(String id) {
        jdbc.update("DELETE FROM dashboard_widget WHERE dashboard_id = ?", id);
        int n = jdbc.update("DELETE FROM dashboard WHERE dashboard_id = ?", id);
        return n > 0 ? Map.of("ok", true, "deleted", id)
                : Map.of("ok", false, "error", "없는 대시보드입니다: " + id);
    }

    // ── 렌더 ────────────────────────────────────────────────────────────────

    /** 데이터셋 기본 대시보드 — 저장 구성이 없으면 자동 초안 */
    public Map<String, Object> datasetDashboard(String datasetId) {
        Map<String, Object> ds = dataset(datasetId);
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> cols = (List<Map<String, Object>>) ds.get("columns");

        String dashboardId = datasetDashboardId(datasetId);
        List<Map<String, Object>> saved = widgetRows(dashboardId);
        boolean draft = saved.isEmpty();
        List<Map<String, Object>> specs = draft
                ? autoDraft(cols, datasetId)
                : saved.stream().map(this::toSpec).toList();

        Map<String, Object> out = renderAll(specs);
        out.put("dashboardId", dashboardId);
        out.put("kind", "dataset");
        out.put("name", str(ds, "name"));
        out.put("dataset", ds);
        out.put("datasets", List.of(ds));   // 편집 화면이 쓰는 후보 목록 (형태를 custom 과 같게 둔다)
        out.put("draft", draft);
        out.put("rowCount", num(ds, "row_count"));
        return out;
    }

    /** 사용자가 만든 대시보드 — 위젯마다 데이터셋이 다를 수 있다 */
    public Map<String, Object> customDashboard(String dashboardId) {
        Map<String, Object> d = lower(jdbc.queryForMap("SELECT * FROM dashboard WHERE dashboard_id = ?", dashboardId));
        List<Map<String, Object>> specs = widgetRows(dashboardId).stream().map(this::toSpec).toList();

        Map<String, Object> out = renderAll(specs);
        out.put("dashboardId", dashboardId);
        out.put("kind", str(d, "kind"));
        out.put("name", str(d, "name"));
        out.put("description", str(d, "description"));
        out.put("showInMenu", d.get("show_in_menu"));
        out.put("draft", false);
        out.put("datasets", datasets());   // 편집 화면이 고를 수 있는 후보
        return out;
    }

    /** 저장하지 않고 계산만 — 편집 중 미리보기 */
    public Map<String, Object> preview(List<Map<String, Object>> widgets) {
        List<Map<String, Object>> specs = new ArrayList<>();
        if (widgets == null) return renderAll(specs);
        for (int i = 0; i < widgets.size(); i++) {
            Map<String, Object> w = new LinkedHashMap<>(widgets.get(i));
            w.put("pos", i);
            w.put("options", withSpan(str(w, "kind"), options(w)));
            specs.add(w);
        }
        return renderAll(specs);
    }

    @Transactional
    public Map<String, Object> saveWidgets(String dashboardId, List<Map<String, Object>> widgets) {
        jdbc.update("DELETE FROM dashboard_widget WHERE dashboard_id = ?", dashboardId);
        String now = LocalDateTime.now().format(TS);
        List<Object[]> batch = new ArrayList<>();
        for (int i = 0; i < widgets.size(); i++) {
            Map<String, Object> w = widgets.get(i);
            String kind = str(w, "kind");
            batch.add(new Object[]{
                    dashboardId + "-W" + i, dashboardId, str(w, "datasetId"), i,
                    kind, str(w, "title"), emptyToNull(str(w, "col")),
                    emptyToNull(str(w, "agg")), str(w, "size").isEmpty() ? "md" : str(w, "size"),
                    toJson(withSpan(kind, options(w))), now});
        }
        jdbc.batchUpdate("""
                INSERT INTO dashboard_widget (widget_id, dashboard_id, dataset_id, pos, kind, title,
                                              col_name, agg, size, options, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, batch);
        jdbc.update("UPDATE dashboard SET updated_at = ? WHERE dashboard_id = ?", now, dashboardId);
        return Map.of("ok", true, "dashboardId", dashboardId, "widgets", widgets.size());
    }

    /** 데이터셋 기본 대시보드 저장 — 대시보드 레코드가 없으면 만들어 붙인다 */
    @Transactional
    public Map<String, Object> saveDatasetWidgets(String datasetId, List<Map<String, Object>> widgets) {
        String dashboardId = datasetDashboardId(datasetId);
        String now = LocalDateTime.now().format(TS);
        Integer exists = jdbc.queryForObject(
                "SELECT COUNT(*) FROM dashboard WHERE dashboard_id = ?", Integer.class, dashboardId);
        if (exists == null || exists == 0) {
            String name = str(jdbc.queryForMap("SELECT name FROM dataset WHERE dataset_id = ?", datasetId), "name");
            jdbc.update("""
                    INSERT INTO dashboard (dashboard_id, name, description, kind, dataset_id, pos,
                                           show_in_menu, created_at, updated_at)
                    VALUES (?,?,?,?,?,0,FALSE,?,?)
                    """, dashboardId, name, "", "dataset", datasetId, now, now);
        }
        // 데이터셋 대시보드의 위젯은 그 데이터셋만 본다
        List<Map<String, Object>> fixed = new ArrayList<>();
        for (Map<String, Object> w : widgets) {
            Map<String, Object> m = new LinkedHashMap<>(w);
            m.put("datasetId", datasetId);
            fixed.add(m);
        }
        return saveWidgets(dashboardId, fixed);
    }

    @Transactional
    public Map<String, Object> resetDatasetWidgets(String datasetId) {
        String dashboardId = datasetDashboardId(datasetId);
        jdbc.update("DELETE FROM dashboard_widget WHERE dashboard_id = ?", dashboardId);
        jdbc.update("DELETE FROM dashboard WHERE dashboard_id = ?", dashboardId);
        return Map.of("ok", true, "datasetId", datasetId, "reset", true);
    }

    private static String datasetDashboardId(String datasetId) {
        return "DB-DS-" + datasetId;
    }

    private List<Map<String, Object>> widgetRows(String dashboardId) {
        return jdbc.queryForList("SELECT * FROM dashboard_widget WHERE dashboard_id = ? ORDER BY pos", dashboardId);
    }

    /** 위젯 목록을 계산해 그릴 수 있는 형태로 만든다 (데이터셋별 행은 한 번만 읽는다) */
    private Map<String, Object> renderAll(List<Map<String, Object>> specs) {
        Map<String, List<Map<String, String>>> rowCache = new HashMap<>();
        Map<String, List<Map<String, Object>>> colCache = new HashMap<>();
        Map<String, String> nameCache = new HashMap<>();

        List<Map<String, Object>> widgets = new ArrayList<>();
        for (Map<String, Object> spec : specs) {
            String dsId = str(spec, "datasetId");
            Map<String, Object> w;
            try {
                int total = datasets.rowCount(dsId);
                if (total > MAX_AGGREGATE_ROWS) {
                    // 전 행을 메모리에 올려 집계하는 구조라 여기가 상한이다.
                    // ponytail: 상한 경고까지. SQL 집계로 내리는 건 payload JSON 파싱이
                    //           H2·PostgreSQL 공통 문법이 없어 별도 작업이다.
                    throw new IllegalStateException(
                            "행 " + total + "건이 집계 상한(" + MAX_AGGREGATE_ROWS + ")을 넘습니다");
                }
                List<Map<String, String>> rows = rowCache.computeIfAbsent(dsId, datasets::rows);
                List<Map<String, Object>> cols = colCache.computeIfAbsent(dsId, this::columns);
                nameCache.computeIfAbsent(dsId, k -> {
                    List<String> n = jdbc.queryForList("SELECT name FROM dataset WHERE dataset_id = ?", String.class, k);
                    return n.isEmpty() ? k : n.get(0);
                });
                w = render(spec, rows, cols);
            } catch (RuntimeException e) {
                // 위젯 하나가 깨져도 나머지는 그린다 (부분 저하 > 전체 실패)
                w = new LinkedHashMap<>(spec);
                w.put("error", "집계 실패: " + e.getMessage());
            }
            w.put("datasetName", nameCache.getOrDefault(dsId, dsId));
            widgets.add(w);
        }

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("widgets", widgets);
        out.put("updatedAt", LocalDateTime.now().format(TS));
        return out;
    }

    /**
     * 컬럼 타입만 보고 초안을 짠다.
     *   전체 건수 KPI → 숫자 컬럼 합계 KPI → 날짜 컬럼 추이 → 범주 컬럼 분포 → 표
     */
    private List<Map<String, Object>> autoDraft(List<Map<String, Object>> cols, String datasetId) {
        List<Map<String, Object>> specs = new ArrayList<>();
        int pos = 0;
        specs.add(spec(pos++, datasetId, "kpi", "전체 건수", null, "count", null));

        List<Map<String, Object>> numbers = byType(cols, "number");
        for (Map<String, Object> c : numbers.subList(0, Math.min(3, numbers.size()))) {
            specs.add(spec(pos++, datasetId, "kpi", str(c, "name") + " 합계", str(c, "name"), "sum", null));
        }

        List<Map<String, Object>> dates = byType(cols, "date");
        if (!dates.isEmpty()) {
            specs.add(spec(pos++, datasetId, "trend", str(dates.get(0), "name") + " 월별 추이",
                    null, "count", opt("group", str(dates.get(0), "name"))));
        }

        // 분포는 고유값이 적은 컬럼일수록 읽기 쉽다
        List<Map<String, Object>> cats = new ArrayList<>(byType(cols, "category"));
        cats.sort(Comparator.comparingInt(c -> num(c, "distinct_n")));
        for (int i = 0; i < Math.min(4, cats.size()); i++) {
            String name = str(cats.get(i), "name");
            specs.add(spec(pos++, datasetId, i == 0 ? "pie" : "bar", name + " 분포",
                    null, "count", opt("group", name)));
        }

        specs.add(spec(pos, datasetId, "table", "데이터 미리보기", null, null, null));
        return specs;
    }

    // ── 집계 ────────────────────────────────────────────────────────────────

    /**
     * 위젯 하나를 계산한다. 뷰 종류와 무관하게 응답 모양은 하나다.
     *
     *   total   : 전체 스칼라 값        percent : 비율(0~100)        unit : 단위
     *   items   : [{name, value, n, percent, children[]}] — 분류가 없으면 1개
     *   (table 만 headers/rows/total 을 쓴다)
     */
    private Map<String, Object> render(Map<String, Object> spec, List<Map<String, String>> rows,
                                       List<Map<String, Object>> cols) {
        Map<String, Object> w = new LinkedHashMap<>(spec);
        String kind = str(spec, "kind");
        Map<String, Object> o = options(spec);

        if ("table".equals(kind)) {
            List<String> names = new ArrayList<>();
            for (Map<String, Object> c : cols) names.add(str(c, "name"));
            w.put("headers", names);
            w.put("rows", rows.subList(0, Math.min(TABLE_ROWS, rows.size())));
            w.put("total", rows.size());
            return w;
        }

        String agg = str(spec, "agg").isEmpty() ? "count" : str(spec, "agg");
        String col = str(spec, "col");
        String g1 = str(o, "group");
        String g2 = str(o, "group2");
        Double target = dbl(o.get("target"));

        Map<String, Object> all = stat(rows, agg, col, o, target);
        // 헤드라인 값(total)은 단위(unit)와 짝이 맞아야 한다 — 진척율의 대표값은 비율이고,
        // 그 비율을 만든 건수는 part/rowCount 로 따로 내려간다.
        w.put("total", "ratio".equals(agg) ? all.get("percent") : all.get("value"));
        w.put("percent", all.get("percent"));
        w.put("part", all.get("part"));
        w.put("rowCount", rows.size());
        w.put("unit", unit(agg, col));

        List<Map<String, Object>> items;
        if ("trend".equals(kind)) {
            items = grouped(rows, g1.isEmpty() ? col : g1, "", agg, col, o, 0, true);
        } else if (!g1.isEmpty()) {
            items = grouped(rows, g1, g2, agg, col, o, topN(o), false);
        } else {
            Map<String, Object> one = new LinkedHashMap<>(all);
            one.put("name", str(spec, "title").isEmpty() ? "전체" : str(spec, "title"));
            items = new ArrayList<>();
            items.add(one);
        }
        share(items, target);
        w.put("items", items);
        return w;
    }

    /** 행 묶음 하나의 지표 — {value, n, part, percent} */
    private Map<String, Object> stat(List<Map<String, String>> rows, String agg, String col,
                                     Map<String, Object> o, Double target) {
        Map<String, Object> m = new LinkedHashMap<>();
        int n = rows.size();
        m.put("n", n);

        if ("ratio".equals(agg)) {
            // 진척율 — 대상 컬럼이 완료로 볼 값인 행의 비율. 값을 안 고르면 빈칸이 아닌 행 기준.
            String match = str(o, "match");
            int part = 0;
            for (Map<String, String> r : rows) {
                String v = r.get(col);
                boolean hit = match.isEmpty()
                        ? v != null && !v.isBlank()
                        : match.equalsIgnoreCase(v == null ? "" : v.trim());
                if (hit) part++;
            }
            m.put("part", part);
            m.put("value", part);
            m.put("percent", n == 0 ? 0d : round(part * 100d / n));
            return m;
        }

        double v = "count".equals(agg) || col.isEmpty() ? n : reduce(rows, col, agg);
        m.put("part", null);
        m.put("value", round(v));
        m.put("percent", target != null && target != 0 ? round(v * 100d / target) : null);
        return m;
    }

    private double reduce(List<Map<String, String>> rows, String col, String agg) {
        List<Double> vals = new ArrayList<>();
        for (Map<String, String> r : rows) {
            Double d = ColumnProfiler.toNumber(r.get(col));
            if (d != null) vals.add(d);
        }
        if (vals.isEmpty()) return 0;
        return switch (agg) {
            case "avg" -> vals.stream().mapToDouble(Double::doubleValue).average().orElse(0);
            case "min" -> vals.stream().mapToDouble(Double::doubleValue).min().orElse(0);
            case "max" -> vals.stream().mapToDouble(Double::doubleValue).max().orElse(0);
            default -> vals.stream().mapToDouble(Double::doubleValue).sum();
        };
    }

    /**
     * 분류 트리 — 1단(g1) 또는 2단(g1 → g2)으로 묶어 각 묶음의 지표를 낸다.
     *
     * @param top     상위 N개만 남기고 나머지는 기타로 합친다 (0이면 전부)
     * @param monthly 날짜 컬럼을 yyyy-MM 으로 묶고 이름 오름차순 (추이)
     */
    private List<Map<String, Object>> grouped(List<Map<String, String>> rows, String g1, String g2,
                                              String agg, String col, Map<String, Object> o,
                                              int top, boolean monthly) {
        List<Map<String, Object>> out = new ArrayList<>();
        if (g1.isEmpty()) return out;
        Function<Map<String, String>, String> key = monthly ? r -> month(r.get(g1)) : r -> label(r.get(g1));

        bucketBy(rows, key).forEach((name, part) -> {
            if (monthly && name.isEmpty()) return;   // 날짜로 못 읽는 행은 추이에서 제외
            Map<String, Object> it = new LinkedHashMap<>(stat(part, agg, col, o, null));
            it.put("name", name);
            if (!g2.isEmpty()) {
                List<Map<String, Object>> kids = new ArrayList<>();
                bucketBy(part, r -> label(r.get(g2))).forEach((kn, kp) -> {
                    Map<String, Object> c = new LinkedHashMap<>(stat(kp, agg, col, o, null));
                    c.put("name", kn);
                    kids.add(c);
                });
                kids.sort(byValueDesc());
                it.put("children", kids);
            }
            out.add(it);
        });

        if (monthly) {
            out.sort(Comparator.comparing(m -> str(m, "name")));
            return out;
        }
        out.sort(byValueDesc());
        return top > 0 ? trim(out, top) : out;
    }

    /** 상위 N + 나머지를 기타 한 줄로 (합칠 때 하위 트리는 버린다) */
    private List<Map<String, Object>> trim(List<Map<String, Object>> items, int top) {
        if (items.size() <= top) return items;
        List<Map<String, Object>> out = new ArrayList<>(items.subList(0, top));
        double v = 0;
        int n = 0;
        for (Map<String, Object> m : items.subList(top, items.size())) {
            Double d = dbl(m.get("value"));
            v += d == null ? 0 : d;
            n += num(m, "n");
        }
        Map<String, Object> etc = new LinkedHashMap<>();
        etc.put("n", n);
        etc.put("part", null);
        etc.put("value", round(v));
        etc.put("percent", null);
        etc.put("name", "기타 " + (items.size() - top) + "종");
        out.add(etc);
        return out;
    }

    /** percent 가 빈 항목을 전체 합 대비 점유율로 채운다 (진척율은 이미 채워져 있어 건드리지 않는다) */
    private void share(List<Map<String, Object>> items, Double target) {
        double sum = 0;
        for (Map<String, Object> i : items) {
            Double d = dbl(i.get("value"));
            sum += d == null ? 0 : d;
        }
        double base = target != null && target != 0 ? target : sum;
        for (Map<String, Object> i : items) {
            Double v = dbl(i.get("value"));
            if (i.get("percent") == null) {
                i.put("percent", base == 0 ? 0d : round((v == null ? 0 : v) * 100d / base));
            }
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> kids = (List<Map<String, Object>>) i.get("children");
            if (kids != null) share(kids, v == null || v == 0 ? null : v);
        }
    }

    private static Map<String, List<Map<String, String>>> bucketBy(
            List<Map<String, String>> rows, Function<Map<String, String>, String> key) {
        Map<String, List<Map<String, String>>> b = new LinkedHashMap<>();
        for (Map<String, String> r : rows) b.computeIfAbsent(key.apply(r), k -> new ArrayList<>()).add(r);
        return b;
    }

    private static Comparator<Map<String, Object>> byValueDesc() {
        return (a, b) -> {
            Double x = dbl(a.get("value"));
            Double y = dbl(b.get("value"));
            return Double.compare(y == null ? 0 : y, x == null ? 0 : x);
        };
    }

    /** 날짜 문자열 → yyyy-MM (못 읽으면 빈 문자열) */
    private static String month(String v) {
        if (v == null) return "";
        String s = v.trim().replace('/', '-').replace('.', '-');
        return s.length() < 7 ? "" : s.substring(0, 7);
    }

    private static String label(String v) {
        return v == null || v.isBlank() ? "(미기재)" : v.trim();
    }

    private static String unit(String agg, String col) {
        if ("ratio".equals(agg)) return "%";
        return "count".equals(agg) || col == null || col.isEmpty() ? "건" : "";
    }

    private static int topN(Map<String, Object> o) {
        Double d = dbl(o.get("top"));
        return d == null || d <= 0 ? TOP_N : d.intValue();
    }

    // ── 유틸 ────────────────────────────────────────────────────────────────

    private Map<String, Object> spec(int pos, String datasetId, String kind, String title,
                                     String col, String agg, Map<String, Object> options) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("pos", pos);
        m.put("datasetId", datasetId);
        m.put("kind", kind);
        m.put("title", title);
        m.put("col", col == null ? "" : col);
        m.put("agg", agg == null ? "" : agg);
        m.put("size", "md");
        m.put("options", withSpan(kind, options));
        return m;
    }

    /** 저장 레코드 → spec. 폭·높이가 없던 옛 위젯도 뷰 기본값으로 채워 그릴 수 있게 한다. */
    private Map<String, Object> toSpec(Map<String, Object> row) {
        String kind = str(row, "kind");
        String col = str(row, "col_name");
        Map<String, Object> o = parse(str(row, "options"));

        // 옛 구성 호환 — bar/donut/trend 는 col 이 분류 컬럼이었다
        if (o.get("group") == null && !col.isEmpty() && GROUP_VIEWS.contains(kind)) {
            o.put("group", col);
            col = "";
        }
        // 옛 크기(sm/md/lg) → 폭 칸수
        if (o.get("w") == null) {
            String size = str(row, "size");
            if ("sm".equals(size)) o.put("w", 3);
            else if ("md".equals(size)) o.put("w", 6);
            else if ("lg".equals(size)) o.put("w", 12);
        }

        Map<String, Object> m = new LinkedHashMap<>();
        m.put("pos", num(row, "pos"));
        m.put("datasetId", str(row, "dataset_id"));
        m.put("kind", kind);
        m.put("title", str(row, "title"));
        m.put("col", col);
        m.put("agg", str(row, "agg"));
        m.put("size", str(row, "size"));
        m.put("options", withSpan(kind, o));
        return m;
    }

    /** 폭·높이 기본값 보정 — 어떤 위젯도 span 없이 내려가지 않게 한다(레이아웃 붕괴 방지) */
    private static Map<String, Object> withSpan(String kind, Map<String, Object> options) {
        Map<String, Object> o = options == null ? new LinkedHashMap<>() : new LinkedHashMap<>(options);
        int[] def = DEFAULT_SPAN.getOrDefault(kind, "table".equals(kind) ? new int[]{12, 3} : new int[]{6, 2});
        Double w = dbl(o.get("w"));
        Double h = dbl(o.get("h"));
        o.put("w", clamp(w == null ? def[0] : w.intValue(), 1, 12));
        o.put("h", clamp(h == null ? def[1] : h.intValue(), 1, 6));
        return o;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> options(Map<String, Object> spec) {
        Object o = spec == null ? null : spec.get("options");
        return o instanceof Map<?, ?> m ? new LinkedHashMap<>((Map<String, Object>) m) : new LinkedHashMap<>();
    }

    private static Map<String, Object> opt(String k, Object v) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put(k, v);
        return m;
    }

    private Map<String, Object> parse(String s) {
        if (s == null || s.isBlank()) return new LinkedHashMap<>();
        try {
            return json.readValue(s, new TypeReference<LinkedHashMap<String, Object>>() {});
        } catch (Exception e) {
            return new LinkedHashMap<>();   // 깨진 옵션은 없는 것으로 본다 (위젯은 그려야 한다)
        }
    }

    private String toJson(Map<String, Object> o) {
        try {
            return o == null || o.isEmpty() ? null : json.writeValueAsString(o);
        } catch (Exception e) {
            return null;
        }
    }

    private static List<Map<String, Object>> byType(List<Map<String, Object>> cols, String type) {
        return cols.stream().filter(c -> type.equals(str(c, "data_type"))).toList();
    }

    private static Map<String, Object> pair(String k1, Object v1, String k2, Object v2) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put(k1, v1);
        m.put(k2, v2);
        return m;
    }

    private static String str(Map<String, ?> m, String k) {
        Object v = m == null ? null : m.get(k);
        return v == null ? "" : String.valueOf(v).trim();
    }

    private static int num(Map<String, ?> m, String k) {
        Double d = dbl(m == null ? null : m.get(k));
        return d == null ? 0 : d.intValue();
    }

    private static Double dbl(Object v) {
        if (v == null) return null;
        if (v instanceof Number n) return n.doubleValue();
        try {
            String s = String.valueOf(v).trim();
            return s.isEmpty() ? null : Double.parseDouble(s);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static int clamp(int v, int lo, int hi) {
        return Math.max(lo, Math.min(hi, v));
    }

    private static String emptyToNull(String s) {
        return s == null || s.isEmpty() ? null : s;
    }

    private static double round(double d) {
        return Math.round(d * 100) / 100d;
    }
}
