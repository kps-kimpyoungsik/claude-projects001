package com.aegis.pm.engine;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import com.aegis.pm.common.Rows;

/**
 * 자료가 사라지거나 바뀐 곳의 이력(refine_trace)과 사람 결정(refine_decision).
 * 원칙: 버리는 곳마다 기록한다 — 기록 없는 삭제는 버그다 (plans/_opens/data_lineage_review §1 P1).
 */
@Service
public class TraceStore {

    public record Trace(String stage, String op, Integer rowRef, String col, String before, String after) {}

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final int MAX_V = 4000;

    private final JdbcTemplate jdbc;

    public TraceStore(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** 같은 데이터셋·단계의 이전 이력을 지우고 새로 쓴다 — 재적재·재정제가 이력을 두 벌 만들지 않게 */
    public void replace(String datasetId, String sourceId, String stage, List<Trace> traces) {
        jdbc.update("DELETE FROM refine_trace WHERE dataset_id = ? AND stage = ?", datasetId, stage);
        add(datasetId, sourceId, traces);
    }

    public void add(String datasetId, String sourceId, List<Trace> traces) {
        if (traces.isEmpty()) return;
        String now = LocalDateTime.now().format(TS);
        List<Object[]> batch = new ArrayList<>(traces.size());
        for (Trace t : traces) {
            batch.add(new Object[] { datasetId, cut(sourceId, 300), t.stage(), t.op(), t.rowRef(), cut(t.col(), 200),
                    cut(t.before(), MAX_V), cut(t.after(), MAX_V), now });
        }
        jdbc.batchUpdate("""
                INSERT INTO refine_trace (dataset_id, source_id, stage, op, row_ref, col_name, before_v, after_v, created_at)
                VALUES (?,?,?,?,?,?,?,?,?)""", batch);
    }

    public List<Map<String, Object>> list(String datasetId) {
        return Rows.lower(jdbc.queryForList("""
                SELECT trace_id, dataset_id, source_id, stage, op, row_ref, col_name, before_v, after_v, created_at
                  FROM refine_trace WHERE dataset_id = ? ORDER BY stage, op, col_name, row_ref, trace_id""", datasetId));
    }

    // ── 사람 결정 ──────────────────────────────────────────────────────────

    public void keep(String sourceId, String op, String col, int rowRef) {
        String c = col == null ? "" : col;
        jdbc.update("DELETE FROM refine_decision WHERE source_id = ? AND op = ? AND col_name = ? AND row_ref = ?", sourceId, op, c, rowRef);
        jdbc.update("INSERT INTO refine_decision (source_id, op, col_name, row_ref, action, decided_at) VALUES (?,?,?,?,'KEEP',?)",
                sourceId, op, c, rowRef, LocalDateTime.now().format(TS));
    }

    public int unkeep(String sourceId, String op, String col, int rowRef) {
        return jdbc.update("DELETE FROM refine_decision WHERE source_id = ? AND op = ? AND col_name = ? AND row_ref = ?",
                sourceId, op, col == null ? "" : col, rowRef);
    }

    public List<Map<String, Object>> decisions(String sourceId) {
        return Rows.lower(jdbc.queryForList(
                "SELECT source_id, op, col_name, row_ref, action, decided_at FROM refine_decision WHERE source_id = ? ORDER BY decided_at", sourceId));
    }

    /** 정제 적용이 묻는 판정 — 이 (op, 열, 행)을 하지 말라는 결정이 있는가 */
    public RefinePlanner.Keep keeper(String sourceId) {
        List<String> keys = new ArrayList<>();
        for (Map<String, Object> d : decisions(sourceId)) {
            keys.add(d.get("op") + "|" + d.get("col_name") + "|" + d.get("row_ref"));
        }
        return RefinePlanner.keep(keys);
    }

    private static String cut(String s, int n) {
        return s == null || s.length() <= n ? s : s.substring(0, n);
    }
}
