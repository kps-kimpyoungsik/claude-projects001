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
    /**
     * 업로드 원본 보관 폴더(UploadService·SourceService 와 같은 상대 경로)와, 기존 평문을 지우지 않고 옮겨 두는 보류 폴더
     * (개인키 사본 확인 전까지의 복구 경로 — 지침 G-9). <b>설정으로만 바꾼다</b> — 필드를 직접 바꾸면 @Transactional 프록시에만
     * 반영되고 실제 객체는 기본값을 쓴다(실측 2026-09-24: 테스트가 실제 data/uploads 19개를 봉인한 사고).
     */
    private final java.nio.file.Path uploadsDir, sourcesDir, holdDir;

    public PiiMigrationService(JdbcTemplate jdbc, PiiVault vault,
                               @org.springframework.beans.factory.annotation.Value("${pm.pii.uploads-dir:data/uploads}") String uploadsDir,
                               @org.springframework.beans.factory.annotation.Value("${pm.pii.sources-dir:data/sources}") String sourcesDir,
                               @org.springframework.beans.factory.annotation.Value("${pm.pii.hold-dir:data/_backup/pre-seal}") String holdDir) {
        this.jdbc = jdbc;
        this.vault = vault;
        this.uploadsDir = java.nio.file.Paths.get(uploadsDir);
        this.sourcesDir = java.nio.file.Paths.get(sourcesDir);
        this.holdDir = java.nio.file.Paths.get(holdDir);
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
                // 역할어("기획")·복합값("고객사,PII-…")은 이미 끝난 값 — 같은 값으로 다시 쓰면 멱등 보고가 거짓이 된다
                String t = vault.tokenize(c.kind(), v);
                if (!t.equals(v)) {
                    n += jdbc.update("UPDATE " + c.table() + " SET " + c.column() + " = ? WHERE " + c.column() + " = ?", t, v);
                }
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
        changed.put("sealed_files", sealFiles(uploadsDir, "upload_batch") + sealFiles(sourcesDir, "source_doc"));
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

    /** 폴더의 평문 원본을 봉인하고, 그 경로를 가리키던 이력 행(stored_path)을 봉인 파일로 바꾼다. 멱등 */
    private int sealFiles(java.nio.file.Path dir, String table) {
        if (!java.nio.file.Files.isDirectory(dir)) return 0;
        int n = 0;
        try (var files = java.nio.file.Files.list(dir)) {
            for (java.nio.file.Path p : files.filter(java.nio.file.Files::isRegularFile)
                    .filter(p -> !p.getFileName().toString().endsWith(".sealed")
                            && !p.getFileName().toString().endsWith(".sealing")).toList()) {
                String before = p.toAbsolutePath().toString();
                java.nio.file.Path s = vault.sealStored(p, holdDir.resolve(dir.getFileName()));
                jdbc.update("UPDATE " + table + " SET stored_path = ? WHERE stored_path = ?", s.toAbsolutePath().toString(), before);
                n++;
            }
        } catch (java.io.IOException e) {
            throw new IllegalStateException("원본 봉인 실패: " + dir, e);
        }
        return n;
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
