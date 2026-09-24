package com.aegis.pm.dds;

import com.aegis.pm.common.Rows;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 도메인 데이터셋(DOM) 생성 — 표준에 안 붙은 컬럼을 <b>버리지 않고 확장 필드로 세운다</b> (04 §2).
 *
 * <h3>DOM 이란</h3>
 * 특정 업무 도메인이 표준에 필드를 더한 것이다. `DOM-여신-SCREEN = STD-SCREEN + {여신등급, 심사단계}`.
 * 표준 질의에 그대로 참여하면서 자기 도메인 필드도 갖는다.
 *
 * <h3>상속에서 필드를 복제하지 않는 이유</h3>
 * DOM 을 만들 때 부모 STD 의 필드를 복사해 두면 편하지만, <b>부모가 바뀌어도 자식이 따라가지
 * 않는다.</b> 필드 정의가 두 벌이 되고 둘이 갈라지면 같은 이름이 계층마다 다른 뜻이 되어
 * 뼈대가 뼈대이기를 그만둔다(04 §2.1 불변식). 그래서 DOM 은 <b>확장 필드만</b> 저장하고
 * 조회 시점에 부모와 합친다({@link #fieldsOf}).
 *
 * <h3>하위는 더할 수만 있다</h3>
 * 부모에 이미 있는 `field_key` 는 확장으로 받지 않는다 — 그게 오버라이드이고, 허용하면
 * 상위 의미를 덮게 된다(04 ADR S3).
 */
@Service
public class DomainBuilder {

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    /** 확장 필드가 몇 개 도메인에서 반복돼야 표준 승격을 제안하는가 */
    static final int PROMOTE_DOMAINS = 2;

    private final JdbcTemplate jdbc;
    private final BindingEngine binding;

    public DomainBuilder(JdbcTemplate jdbc, BindingEngine binding) {
        this.jdbc = jdbc;
        this.binding = binding;
    }

    /**
     * 데이터셋의 미바인딩 컬럼을 확장 필드로 삼아 DOM 엔티티를 만든다.
     *
     * @param datasetId 확장의 근거가 되는 데이터셋 (이미 부모 STD 에 부분 바인딩돼 있어야 한다)
     * @param domain    도메인 이름 (`여신`·`수신` …)
     */
    @Transactional
    public Map<String, Object> create(String datasetId, String domain) {
        Map<String, Object> ds = Rows.lower(jdbc.queryForMap(
                "SELECT dataset_id, name, std_id, bind_ratio, ds_level FROM dataset WHERE dataset_id = ?",
                datasetId));
        String parent = str(ds.get("std_id"));
        if (parent == null || parent.isBlank()) {
            throw new IllegalArgumentException(
                    "이 데이터셋은 표준에 붙지 않았습니다. 도메인은 표준의 확장이므로 부모가 필요합니다 — "
                    + "먼저 바인딩하거나, 표준에 없는 새 종류라면 표준 신설을 검토하세요.");
        }
        if (domain == null || domain.isBlank()) {
            throw new IllegalArgumentException("도메인 이름이 필요합니다 (예: 여신·수신)");
        }

        List<String> ext = binding.unbound(datasetId).stream()
                .filter(c -> !c.trim().matches("col\\d+"))   // 자리표시자는 필드가 아니다
                .toList();
        if (ext.isEmpty()) {
            throw new IllegalArgumentException(
                    "확장할 컬럼이 없습니다 — 이 표는 부모 표준으로 이미 전부 설명됩니다.");
        }

        String stdId = "DOM-" + domain + "-" + parent.replace("STD-", "");
        String now = LocalDateTime.now().format(TS);
        Map<String, Object> parentRow = Rows.lower(jdbc.queryForMap(
                "SELECT name, grain, purpose FROM standard_dataset WHERE std_id = ?", parent));

        jdbc.update("DELETE FROM standard_dataset WHERE std_id = ?", stdId);
        jdbc.update("""
                INSERT INTO standard_dataset (std_id, level, parent_std, name, domain, purpose,
                                              grain, owner, version, status, created_at, updated_at)
                VALUES (?,'DOM',?,?,?,?,?,?, '1.0.0','draft',?,?)
                """, stdId, parent, domain + " " + parentRow.get("name"), domain,
                domain + " 도메인이 " + parent + " 에 더한 확장 — 근거 데이터셋: " + ds.get("name"),
                parentRow.get("grain"), domain + " 오너", now, now);

        // 부모에 이미 있는 field_key 는 확장으로 받지 않는다 (오버라이드 금지)
        List<String> parentKeys = jdbc.queryForList(
                "SELECT field_key FROM standard_field WHERE std_id = ?", String.class, parent);

        jdbc.update("DELETE FROM standard_field WHERE std_id = ?", stdId);
        List<String> added = new ArrayList<>();
        List<String> skipped = new ArrayList<>();
        for (String col : ext) {
            String key = fieldKey(col);
            if (parentKeys.contains(key)) {
                skipped.add(col + "(부모에 이미 있음 — 오버라이드 금지)");
                continue;
            }
            jdbc.update("""
                    INSERT INTO standard_field (std_id, field_key, label, role, data_type, required,
                                                unit, code_set, definition, intent, synonyms, is_ext)
                    VALUES (?,?,?,?,?,FALSE,NULL,NULL,?,?,?,TRUE)
                    """, stdId, key, col, roleOf(datasetId, col), typeOf(datasetId, col),
                    "(자동 초안) " + domain + " 도메인 고유 컬럼 — 표준에 없어 확장으로 세웠다",
                    "표준으로 설명되지 않는 부분을 버리지 않고 남긴다",
                    col);
            added.add(col);
        }

        // 근거 데이터셋을 이 DOM 의 인스턴스로 올린다 — 이제 확장 필드까지 설명된다
        jdbc.update("UPDATE dataset SET std_id = ?, ds_level = 'DOM' WHERE dataset_id = ?", stdId, datasetId);
        for (String col : added) {
            binding.correctAuto(datasetId, col, stdId, fieldKey(col),
                    "도메인 확장 필드로 세움 (" + domain + ")");
        }

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("std_id", stdId);
        out.put("parent_std", parent);
        out.put("domain", domain);
        out.put("ext_fields", added);
        out.put("skipped", skipped);
        out.put("note", "부모 " + parent + " 의 필드는 복제하지 않는다 — 조회 시 합쳐지므로 부모가 바뀌면 함께 바뀐다");
        return out;
    }

    /** DOM 의 전체 필드 = 부모 상속분 + 자기 확장분. 복제가 아니라 조회 시 합친다 */
    public List<Map<String, Object>> fieldsOf(String stdId) {
        Map<String, Object> row = Rows.lower(jdbc.queryForMap(
                "SELECT level, parent_std FROM standard_dataset WHERE std_id = ?", stdId));
        List<Map<String, Object>> out = new ArrayList<>();
        String parent = str(row.get("parent_std"));
        if (parent != null && !parent.isBlank()) {
            for (Map<String, Object> f : Rows.lower(jdbc.queryForList(
                    "SELECT * FROM standard_field WHERE std_id = ? ORDER BY required DESC, field_key", parent))) {
                f.put("inherited_from", parent);
                out.add(f);
            }
        }
        out.addAll(Rows.lower(jdbc.queryForList(
                "SELECT * FROM standard_field WHERE std_id = ? ORDER BY field_key", stdId)));
        return out;
    }

    public List<Map<String, Object>> domains() {
        return Rows.lower(jdbc.queryForList(
                "SELECT * FROM standard_dataset WHERE level = 'DOM' ORDER BY domain, std_id"));
    }

    /**
     * 표준 승격 제안 — 같은 확장 필드가 여러 도메인에서 반복되면 그건 도메인 고유가 아니다.
     *
     * <p><b>제안만 한다</b>(05 ADR V5 와 같은 이유). 표준은 합의이고 빈도는 합의의 근거일 뿐이다.
     * 올리는 것은 사람이고, 올리는 순간 그 필드는 모든 하위에 상속되므로 되돌리기가 비싸다.
     */
    public List<Map<String, Object>> promotions() {
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> r : Rows.lower(jdbc.queryForList("""
                SELECT f.field_key, f.label, COUNT(DISTINCT d.domain) AS domains,
                       MIN(d.parent_std) AS parent_std
                  FROM standard_field f JOIN standard_dataset d ON d.std_id = f.std_id
                 WHERE f.is_ext = TRUE AND d.level = 'DOM' AND d.status <> 'deprecated'
                 GROUP BY f.field_key, f.label
                """))) {
            int n = ((Number) r.get("domains")).intValue();
            if (n < PROMOTE_DOMAINS) continue;
            r.put("suggest", "표준 승격 후보");
            r.put("why", "도메인 " + n + "곳이 같은 확장 필드를 쓴다 — 도메인 고유가 아니다");
            r.put("caution", "승격하면 모든 하위가 상속받는다. 되돌리기가 비싸므로 사람이 판단한다");
            out.add(r);
        }
        out.sort((a, b) -> ((Number) b.get("domains")).intValue() - ((Number) a.get("domains")).intValue());
        return out;
    }

    // ── 보조 ────────────────────────────────────────────────────────────────

    /** 한글 컬럼명을 시스템 키로 — 표기가 그대로 키가 되면 표기가 바뀔 때 키가 깨진다 */
    static String fieldKey(String colName) {
        String norm = Absorb.norm(Ingest.nameOf(colName));
        return "ext_" + Integer.toHexString(norm.hashCode()).replace("-", "n");
    }

    /** 이 컬럼의 업무 의미(role) 를 물리 타입에서 추정한다 — 확장 필드도 role 이 있어야 질의에 쓰인다 */
    private String roleOf(String datasetId, String col) {
        String type = typeOf(datasetId, col);
        return switch (type) {
            case "number" -> "measure";
            case "date" -> "time";
            case "category" -> "status";
            default -> "text";
        };
    }

    private String typeOf(String datasetId, String col) {
        List<String> t = jdbc.queryForList(
                "SELECT data_type FROM dataset_column WHERE dataset_id = ? AND name = ?",
                String.class, datasetId, col);
        return t.isEmpty() || t.get(0) == null ? "text" : t.get(0);
    }

    private static String str(Object o) {
        return o == null ? null : String.valueOf(o);
    }
}
