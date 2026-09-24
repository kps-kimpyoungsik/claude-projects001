package com.aegis.pm.dataset;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * 데이터셋 저장 계층 — 표(헤더 + 행) 하나를 dataset 3형제 테이블에 쓴다.
 *
 * 엑셀 적재(DatasetIngestService)와 Core 부속 시트 적재(이슈·투입인력)가 같은 창구를 쓴다.
 * 저장 모델이 하나뿐이어야 "이 데이터가 어디에 있나"가 헷갈리지 않는다.
 */
@Service
public class DatasetWriter {

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final JdbcTemplate jdbc;
    private final ObjectMapper json = new ObjectMapper();
    /** 뷰 데이터셋의 행 공급자 — 순환 의존을 피하려 선택 주입한다 */
    private final com.aegis.pm.dds.CoreView coreView;

    public DatasetWriter(JdbcTemplate jdbc,
                         @org.springframework.beans.factory.annotation.Autowired(required = false)
                         com.aegis.pm.dds.CoreView coreView) {
        this.jdbc = jdbc;
        this.coreView = coreView;
    }

    /** 데이터셋 1개를 통째로 교체 저장 */
    @Transactional
    public int write(String datasetId, String name, String sheetName, String sourceFile, String batchId,
                     List<String> headers, List<Map<String, String>> rows) {
        String now = LocalDateTime.now().format(TS);

        jdbc.update("DELETE FROM dataset_row WHERE dataset_id = ?", datasetId);
        jdbc.update("DELETE FROM dataset_column WHERE dataset_id = ?", datasetId);
        jdbc.update("DELETE FROM dataset WHERE dataset_id = ?", datasetId);

        jdbc.update("""
                INSERT INTO dataset (dataset_id, name, sheet_name, source_file, batch_id,
                                     row_count, col_count, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """, datasetId, cut(name, 200), cut(sheetName, 200), cut(sourceFile, 300),
                batchId, rows.size(), headers.size(), now, now);

        List<Object[]> rowBatch = new ArrayList<>();
        for (int i = 0; i < rows.size(); i++) {
            rowBatch.add(new Object[]{datasetId, i, toJson(rows.get(i))});
        }
        jdbc.batchUpdate("INSERT INTO dataset_row (dataset_id, row_no, payload) VALUES (?,?,?)", rowBatch);

        List<Object[]> colBatch = new ArrayList<>();
        for (int c = 0; c < headers.size(); c++) {
            colBatch.add(ColumnProfiler.profile(datasetId, c, headers.get(c), rows));
        }
        jdbc.batchUpdate("""
                INSERT INTO dataset_column (dataset_id, col_no, name, data_type, distinct_n, null_n,
                                            min_v, max_v, sum_v)
                VALUES (?,?,?,?,?,?,?,?,?)
                """, colBatch);
        return rows.size();
    }

    /** 헤더 순서를 보존한 채 읽는다 (dataset_column 순서 = 원본 컬럼 순서) */
    public List<String> headers(String datasetId) {
        return jdbc.queryForList(
                "SELECT name FROM dataset_column WHERE dataset_id = ? ORDER BY col_no", String.class, datasetId);
    }

    public List<Map<String, String>> rows(String datasetId) {
        return rows(datasetId, 0);
    }

    /**
     * 행을 읽는다. limit &gt; 0 이면 DB에서 잘라 온다 —
     * 미리보기용 200행을 위해 수만 행을 메모리에 올리지 않기 위해서다.
     */
    public List<Map<String, String>> rows(String datasetId, int limit) {
        // 뷰 데이터셋은 행을 복사해 두지 않았다 — 원본 테이블에서 읽는다(같은 사실이 두 벌이
        // 되지 않게 하기 위함). 호출부는 뷰인지 아닌지 알 필요가 없다.
        if (coreView != null && com.aegis.pm.dds.CoreView.isView(datasetId)) {
            return coreView.rows(datasetId, limit);
        }
        String sql = "SELECT payload FROM dataset_row WHERE dataset_id = ? ORDER BY row_no"
                + (limit > 0 ? " LIMIT " + limit : "");   // limit 은 호출부에서 온 정수 — 바인딩 대신 검증 후 삽입
        List<Map<String, String>> out = new ArrayList<>();
        for (String p : jdbc.queryForList(sql, String.class, datasetId)) {
            out.add(fromJson(p));
        }
        return out;
    }

    /**
     * 행을 하나씩 흘려보낸다 — 집계처럼 전 행을 보되 전 행을 <b>담을</b> 필요는 없을 때 쓴다.
     * List 를 만들지 않으므로 같은 작업에서 메모리 사용이 행 1건 수준으로 유지된다.
     */
    public void forEachRow(String datasetId, Consumer<Map<String, String>> fn) {
        // 뷰는 행을 복사해 두지 않았다 — 원본에서 읽는다. rows() 와 같은 이유로 분기한다.
        // 이 분기가 없으면 뷰의 집계가 조용히 0건이 된다(오류가 아니라 빈 결과라 더 위험하다).
        if (coreView != null && com.aegis.pm.dds.CoreView.isView(datasetId)) {
            coreView.rows(datasetId, 0).forEach(fn);
            return;
        }
        jdbc.query("SELECT payload FROM dataset_row WHERE dataset_id = ? ORDER BY row_no",
                rs -> { fn.accept(fromJson(rs.getString(1))); }, datasetId);
    }

    /** 적재 시 기록해 둔 행 수 — 전 행을 읽기 전에 규모를 먼저 보려고 쓴다 */
    public int rowCount(String datasetId) {
        List<Integer> n = jdbc.queryForList(
                "SELECT row_count FROM dataset WHERE dataset_id = ?", Integer.class, datasetId);
        return n.isEmpty() || n.get(0) == null ? 0 : n.get(0);
    }

    public boolean exists(String datasetId) {
        Integer n = jdbc.queryForObject("SELECT COUNT(*) FROM dataset WHERE dataset_id = ?", Integer.class, datasetId);
        return n != null && n > 0;
    }

    /** 행 1건의 특정 값만 바꾼다 (이슈 완료여부 저장 등) */
    @Transactional
    public boolean updateCell(String datasetId, int rowNo, Map<String, String> changes) {
        List<String> payloads = jdbc.queryForList(
                "SELECT payload FROM dataset_row WHERE dataset_id = ? AND row_no = ?", String.class, datasetId, rowNo);
        if (payloads.isEmpty()) return false;
        Map<String, String> row = fromJson(payloads.get(0));
        row.putAll(changes);
        jdbc.update("UPDATE dataset_row SET payload = ? WHERE dataset_id = ? AND row_no = ?",
                toJson(row), datasetId, rowNo);
        return true;
    }

    /**
     * 값이 일치하는 첫 행 번호 (없으면 -1).
     *
     * payload 안의 `"컬럼":"값"` 조각으로 후보를 DB에서 먼저 좁힌 뒤 자바에서 정확히 확인한다 —
     * LIKE 는 후보를 넓힐 뿐 좁히지 않으므로(값에 %·_ 가 있어도 누락 없음) 결과는 전량 스캔과 같다.
     */
    public int findRow(String datasetId, String column, String value) {
        if (value == null) return -1;
        String like = "%" + literal(column) + ":" + literal(value) + "%";
        List<Object[]> hits = jdbc.query(
                "SELECT row_no, payload FROM dataset_row WHERE dataset_id = ? AND payload LIKE ? ORDER BY row_no",
                (rs, i) -> new Object[]{rs.getInt(1), rs.getString(2)}, datasetId, like);
        for (Object[] h : hits) {
            if (value.equals(fromJson((String) h[1]).get(column))) return (Integer) h[0];
        }
        return -1;
    }

    /**
     * 문자열을 payload 안에 들어간 그대로(JSON 이스케이프 포함) 만든 뒤 LIKE 패턴으로 쓸 수 있게 한다.
     * H2·PostgreSQL 모두 LIKE 의 기본 escape 문자가 `\` 라서, JSON 이스케이프의 `\` 를 그대로 두면
     * 패턴이 한 번 더 풀려 원문과 어긋난다(값에 따옴표가 있으면 못 찾는다).
     */
    private String literal(String s) {
        String jsonText;
        try {
            jsonText = json.writeValueAsString(s);
        } catch (Exception e) {
            jsonText = "\"" + s + "\"";
        }
        return jsonText.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_");
    }

    private static String cut(String s, int n) {
        return s == null || s.length() <= n ? s : s.substring(0, n);
    }

    private String toJson(Map<String, String> row) {
        try {
            return json.writeValueAsString(row);
        } catch (Exception e) {
            throw new IllegalStateException("행 직렬화 실패: " + e.getMessage(), e);
        }
    }

    private Map<String, String> fromJson(String payload) {
        try {
            return json.readValue(payload, new TypeReference<LinkedHashMap<String, String>>() {});
        } catch (Exception e) {
            return new LinkedHashMap<>();
        }
    }
}
