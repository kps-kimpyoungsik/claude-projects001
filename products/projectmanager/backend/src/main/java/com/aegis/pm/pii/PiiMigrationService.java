package com.aegis.pm.pii;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * 기존 평문 → 토큰 전환 (설계서 §7). 멱등 — 이미 토큰인 값은 건너뛴다.
 *
 * <p>개인키가 없거나 왕복 시험이 실패하면 아무것도 바꾸지 않는다. 개인키 없이 전환하면 원문을 영영 못 되찾는다.
 */
@Service
public class PiiMigrationService {

    private final JdbcTemplate jdbc;
    private final PiiVault vault;
    private final ObjectMapper json = new ObjectMapper();   // 저장용 — HTTP 공용 매퍼를 쓰면 마스크가 저장된다

    public PiiMigrationService(JdbcTemplate jdbc, PiiVault vault) {
        this.jdbc = jdbc;
        this.vault = vault;
    }

    /** 남아 있는 평문 개수 — 전환 전후 비교·상태 화면용 */
    public Map<String, Object> status() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("enabled", vault.enabled());
        out.put("privateKey", vault.canDecrypt());
        out.put("reveal", vault.revealing());
        out.put("vault", jdbc.queryForObject("SELECT COUNT(*) FROM pii_vault", Integer.class));
        // 아직 바꿀 것이 남은 행 — 역할어("기획")·"고객사,PII-…" 복합값은 이미 끝난 상태라 세지 않는다
        Map<String, Integer> plain = new LinkedHashMap<>();
        for (PiiRegistry.Column c : PiiRegistry.COLUMNS) {
            int n = 0;
            for (Map<String, Object> r : jdbc.queryForList("SELECT " + c.column() + " v, COUNT(*) n FROM " + c.table()
                    + " WHERE " + c.column() + " IS NOT NULL AND " + c.column() + " <> '' GROUP BY " + c.column())) {
                String v = (String) r.get("v");
                if (vault.enabled() ? !vault.tokenOf(c.kind(), v).equals(v) : true) n += ((Number) r.get("n")).intValue();
            }
            plain.put(c.table() + "." + c.column(), n);
        }
        out.put("plaintext", plain);
        return out;
    }

    @Transactional
    public Map<String, Object> migrate() {
        vault.verifyRoundTrip();
        Map<String, Integer> changed = new LinkedHashMap<>();
        for (PiiRegistry.Column c : PiiRegistry.COLUMNS) {
            int n = 0;
            for (String v : jdbc.queryForList("SELECT DISTINCT " + c.column() + " FROM " + c.table() + " WHERE "
                    + c.column() + " IS NOT NULL AND " + c.column() + " <> '' AND " + c.column() + " NOT LIKE 'PII-%'",
                    String.class)) {
                n += jdbc.update("UPDATE " + c.table() + " SET " + c.column() + " = ? WHERE " + c.column() + " = ?",
                        vault.tokenize(c.kind(), v), v);
            }
            changed.put(c.table() + "." + c.column(), n);
        }
        // 순서가 중요하다 — 본문 속 이름은 금고에 있는 사람만 찾는다. 데이터셋 1차에서 시트에만 있는 사람까지 금고에
        // 올리고, 그 다음 본문을 훑고, 데이터셋 2차에서 앞 행 본문을 다시 훑는다(멱등이라 두 번 돌아도 같다).
        int dsFirst = migrateDatasets();
        for (PiiRegistry.Column c : PiiRegistry.TEXT_COLUMNS) {
            int n = 0;
            for (String v : jdbc.queryForList("SELECT DISTINCT " + c.column() + " FROM " + c.table() + " WHERE "
                    + c.column() + " IS NOT NULL AND " + c.column() + " <> ''", String.class)) {
                String s = vault.scrub(v);
                if (!s.equals(v)) {
                    n += jdbc.update("UPDATE " + c.table() + " SET " + c.column() + " = ? WHERE " + c.column() + " = ?", s, v);
                }
            }
            changed.put(c.table() + "." + c.column() + "(본문)", n);
        }
        changed.put("dataset_row", dsFirst + migrateDatasets());
        Map<String, Object> out = new LinkedHashMap<>(status());
        out.put("changed", changed);
        return out;
    }

    /**
     * 업로드 시트 — P2 칸은 토큰, 나머지 칸은 본문 속 이름, 이름이 헤더인 컬럼은 헤더까지(바인딩·위젯 참조 포함).
     * 바뀐 컬럼의 min/max(원문이 들어 있다)는 지운다.
     */
    private int migrateDatasets() {
        int rows = 0;
        for (String ds : jdbc.queryForList("SELECT dataset_id FROM dataset", String.class)) {
            Map<String, String> renamed = new LinkedHashMap<>();
            for (String h : jdbc.queryForList("SELECT name FROM dataset_column WHERE dataset_id = ?", String.class, ds)) {
                String s = vault.scrub(h);
                if (!s.equals(h)) renamed.put(h, s);
            }
            renamed.forEach((h, s) -> {
                jdbc.update("UPDATE dataset_column SET name = ?, min_v = NULL, max_v = NULL WHERE dataset_id = ? AND name = ?", s, ds, h);
                jdbc.update("UPDATE dataset_binding SET col_name = ? WHERE dataset_id = ? AND col_name = ?", s, ds, h);
                jdbc.update("UPDATE binding_label SET col_name = ? WHERE dataset_id = ? AND col_name = ?", s, ds, h);
                jdbc.update("UPDATE dashboard_widget SET col_name = ? WHERE dataset_id = ? AND col_name = ?", s, ds, h);
            });
            Map<String, String> kinds = new LinkedHashMap<>();
            for (String h : jdbc.queryForList("SELECT name FROM dataset_column WHERE dataset_id = ?", String.class, ds)) {
                String k = PiiRegistry.kindOfHeader(h);
                if (k != null) kinds.put(h, k);
            }
            for (Map<String, Object> r : jdbc.queryForList(
                    "SELECT row_no, payload FROM dataset_row WHERE dataset_id = ?", ds)) {
                Object no = r.containsKey("ROW_NO") ? r.get("ROW_NO") : r.get("row_no");
                String payload = (String) (r.containsKey("PAYLOAD") ? r.get("PAYLOAD") : r.get("payload"));
                Map<String, String> row = read(payload);
                boolean dirty = false;
                for (var e : renamed.entrySet()) {
                    if (row.containsKey(e.getKey())) { row.put(e.getValue(), row.remove(e.getKey())); dirty = true; }
                }
                for (var e : row.entrySet()) {
                    String v = e.getValue();
                    String k = kinds.get(e.getKey());
                    String t = k != null ? vault.tokenize(k, v) : vault.scrub(v);
                    if (v != null && !v.equals(t)) { e.setValue(t); dirty = true; }
                }
                if (dirty) {
                    jdbc.update("UPDATE dataset_row SET payload = ? WHERE dataset_id = ? AND row_no = ?", write(row), ds, no);
                    rows++;
                }
            }
            for (String h : kinds.keySet()) {
                jdbc.update("UPDATE dataset_column SET min_v = NULL, max_v = NULL WHERE dataset_id = ? AND name = ?", ds, h);
            }
        }
        return rows;
    }

    private Map<String, String> read(String payload) {
        try {
            return json.readValue(payload, new TypeReference<LinkedHashMap<String, String>>() {});
        } catch (Exception e) {
            throw new IllegalStateException("payload 해석 실패", e);
        }
    }

    private String write(Map<String, String> row) {
        try {
            return json.writeValueAsString(row);
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }
}
