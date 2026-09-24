package com.aegis.pm.repo;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import com.aegis.pm.domain.Summary;
import com.aegis.pm.domain.Task;
import com.aegis.pm.domain.WbsModel;
import com.aegis.pm.dataset.CoreDatasets;
import com.aegis.pm.dataset.DatasetWriter;
import com.aegis.pm.excel.IssueTable;
import com.aegis.pm.excel.SheetTableReader.Table;

/**
 * DB 어댑터 — `wbs.source: db` 일 때 활성화된다.
 *
 * 엑셀을 한 번 import 해두면(WbsImportService) 이후로는 엑셀 파일 없이 동작한다.
 * 스키마는 schema.sql 하나뿐이라 H2 → PostgreSQL 전환은 datasource 설정 교체로 끝난다.
 */
@Repository
@ConditionalOnProperty(name = "wbs.source", havingValue = "db")
public class JdbcWbsRepository implements WbsRepository {

    private final JdbcTemplate jdbc;
    private final DatasetWriter datasets;

    public JdbcWbsRepository(JdbcTemplate jdbc, DatasetWriter datasets) {
        this.jdbc = jdbc;
        this.datasets = datasets;
    }

    @Override
    public WbsModel model() {
        Map<String, String> meta = meta();
        if (meta.isEmpty()) {
            throw new IllegalStateException(
                    "DB에 적재된 WBS가 없습니다. POST /api/admin/import 로 엑셀을 먼저 업로드하세요.");
        }

        List<Task> tasks = jdbc.query("""
                SELECT seq, no, dep, name, path, big, mid, small,
                       p_start, p_end, owner, part, p_prog,
                       a_start, a_end, a_prog, weight, note,
                       week, start_week, end_week, is_leaf, status
                  FROM wbs_task ORDER BY seq
                """, (rs, i) -> new Task(
                rs.getInt("seq"),
                (Integer) rs.getObject("no"),
                rs.getInt("dep"),
                rs.getString("name"),
                rs.getString("path"),
                rs.getString("big"),
                rs.getString("mid"),
                rs.getString("small"),
                rs.getString("p_start"),
                rs.getString("p_end"),
                rs.getString("owner"),
                rs.getString("part"),
                (Double) rs.getObject("p_prog"),
                rs.getString("a_start"),
                rs.getString("a_end"),
                (Double) rs.getObject("a_prog"),
                (Double) rs.getObject("weight"),
                rs.getString("note"),
                (Integer) rs.getObject("week"),
                (Integer) rs.getObject("start_week"),
                (Integer) rs.getObject("end_week"),
                rs.getBoolean("is_leaf"),
                rs.getString("status")));

        Summary summary = new Summary(
                dbl(meta.get("summary_p_prog")),
                dbl(meta.get("summary_a_prog")),
                dbl(meta.get("summary_spi")),
                meta.get("as_of"));

        return new WbsModel(summary, tasks,
                meta.get("base"),
                Integer.parseInt(meta.getOrDefault("max_week", "0")),
                meta.getOrDefault("project_name", ""),
                meta.getOrDefault("as_of", ""),
                LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
    }

    @Override
    public Table table(String logical) {
        String datasetId = CoreDatasets.of(logical);
        if (datasetId == null || !datasets.exists(datasetId)) return new Table(false, List.of(), List.of());
        return new Table(true, datasets.headers(datasetId), datasets.rows(datasetId));
    }

    /** 이슈 완료여부 저장 — 이슈 데이터셋의 해당 행만 갱신 (원본 setIssueStatus 동작 이관) */
    @Override
    public Map<String, Object> updateIssueStatus(String no, boolean done) {
        String ds = CoreDatasets.ISSUES;
        if (!datasets.exists(ds)) return Map.of("ok", false, "error", "이슈 데이터가 적재돼 있지 않습니다.");

        String doneCol = null, updCol = null;
        List<String> headers = datasets.headers(ds);
        if (!headers.contains(IssueTable.NO_COL)) {
            return Map.of("ok", false, "error", "이슈 데이터에 '순번' 컬럼이 없습니다.");
        }
        for (String h : headers) {
            if (doneCol == null && IssueTable.DONE_COL.matcher(h).find()) doneCol = h;
            else if (updCol == null && IssueTable.UPDATED_COL.matcher(h).find()) updCol = h;
        }
        if (doneCol == null) return Map.of("ok", false, "error", "이슈 데이터에 '완료여부' 컬럼이 없습니다.");

        int rowNo = datasets.findRow(ds, IssueTable.NO_COL, no);
        if (rowNo < 0) return Map.of("ok", false, "error", "순번 " + no + " 행을 찾지 못했습니다.");

        String value = done ? "완료" : "진행중";
        Map<String, String> changes = new LinkedHashMap<>();
        changes.put(doneCol, value);
        if (updCol != null) {
            changes.put(updCol, LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
        }
        datasets.updateCell(ds, rowNo, changes);
        return Map.of("ok", true, "no", no, "status", value);
    }

    @Override
    public String describe() {
        Map<String, String> meta = meta();
        return "db (imported=" + meta.getOrDefault("imported_at", "없음")
                + ", source=" + meta.getOrDefault("source_file", "-") + ")";
    }

    private Map<String, String> meta() {
        Map<String, String> m = new LinkedHashMap<>();
        jdbc.queryForList("SELECT meta_key, meta_value FROM wbs_meta")
                .forEach(r -> m.put(String.valueOf(r.get("meta_key")),
                        r.get("meta_value") == null ? null : String.valueOf(r.get("meta_value"))));
        return m;
    }

    private static Double dbl(String s) {
        try {
            return s == null ? null : Double.valueOf(s);
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
