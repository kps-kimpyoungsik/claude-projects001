package com.aegis.pm.unittest;

import com.aegis.pm.common.Rows;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 결함(기획요청) 관리 — 조회·집계·CRUD + **IA 기획 피드백 이벤트 자동 등록**.
 *
 * 원본은 10분 트리거가 구글시트에 행을 덧붙였다(IaFeedbackSync.js).
 * 여기서는 같은 규칙으로 DB(defect)에 등록한다:
 *   - IA 기획검토상태 = '기획 피드백' 인 화면만 대상
 *   - 같은 화면(Screen ID)의 마지막 기록과 검토내용이 같으면 추가하지 않음(해시 비교)
 *   - 내용이 바뀌면 새 결함으로 1건 추가 (기존 건은 수정하지 않음 — 이력 보존)
 */
@Service
public class DefectService {

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final DateTimeFormatter YMD = DateTimeFormatter.ofPattern("yyyy-MM-dd");
    private static final Pattern HASH_TAG = Pattern.compile("#([A-Za-z0-9_-]{10})$");

    /** 자동수집 표시 — 원본 IAFB.TAG */
    private static final String AUTO_TAG = "IA 화면목록 기획 피드백 자동 수집";
    /** 원본 IAFB.DEF 기본값 */
    private static final String DEF_TYPE = "기능오류", DEF_SEV = "보통", DEF_PRIO = "중";
    private static final String ST_DONE = "조치완료", ST_OTHER = "대기";

    private final JdbcTemplate jdbc;
    private final IaScopeService ia;

    public DefectService(JdbcTemplate jdbc, IaScopeService ia) {
        this.jdbc = jdbc;
        this.ia = ia;
    }

    // ── 조회 ────────────────────────────────────────────────────────────────

    public List<Map<String, Object>> list(String status, String q) {
        return list(status, q, null, null);
    }

    /**
     * @param source  excel | manual | ia-event (엑셀로 들어온 건 / 화면 등록분 / IA 이벤트 구분)
     * @param batchId 특정 업로드 배치로 들어온 건만
     */
    public List<Map<String, Object>> list(String status, String q, String source, String batchId) {
        StringBuilder sql = new StringBuilder("""
                SELECT defect_id, reg_dt, wbs_id, req_id, system_name, screen, def_type, severity, priority,
                       content, repro, finder, owner, status, action, done_dt, retest, remark,
                       source, batch_id, created_at, updated_at
                  FROM defect WHERE 1=1
                """);
        List<Object> args = new ArrayList<>();
        if (status != null && !status.isBlank()) {
            sql.append(" AND status = ?");
            args.add(status);
        }
        if (source != null && !source.isBlank()) {
            sql.append(" AND source = ?");
            args.add(source);
        }
        if (batchId != null && !batchId.isBlank()) {
            sql.append(" AND batch_id = ?");
            args.add(batchId);
        }
        if (q != null && !q.isBlank()) {
            sql.append(" AND (LOWER(defect_id) LIKE ? OR LOWER(screen) LIKE ? OR LOWER(content) LIKE ? OR LOWER(owner) LIKE ?)");
            String like = "%" + q.toLowerCase() + "%";
            args.add(like); args.add(like); args.add(like); args.add(like);
        }
        sql.append(" ORDER BY defect_id DESC");
        // H2 는 컬럼 키를 대문자로, PostgreSQL 은 소문자로 준다. 화면(`Defects.jsx`)은
        // `r.defect_id` 로 읽으므로 대문자를 그대로 내보내면 **전 필드가 undefined** 가 된다.
        return Rows.lower(jdbc.queryForList(sql.toString(), args.toArray()));
    }

    /** 원본 getDefectDashJson() 형태 — 화면이 그대로 쓴다 */
    public Map<String, Object> dashboard() {
        List<Map<String, Object>> rows = list(null, null);
        Map<String, Integer> st = new LinkedHashMap<>(), sv = new LinkedHashMap<>(),
                ty = new LinkedHashMap<>(), ow = new LinkedHashMap<>(), sr = new LinkedHashMap<>();

        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> r : rows) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", nz(r.get("defect_id")));
            row.put("regdt", nz(r.get("reg_dt")));
            row.put("req", nz(r.get("req_id")));
            row.put("screen", nz(r.get("screen")));
            row.put("type", nz(r.get("def_type")));
            row.put("sev", nz(r.get("severity")));
            row.put("prio", nz(r.get("priority")));
            row.put("content", nz(r.get("content")));
            row.put("owner", nz(r.get("owner")));
            String status = nz(r.get("status")).isEmpty() ? "(미기재)" : nz(r.get("status"));
            row.put("status", status);
            row.put("action", nz(r.get("action")));
            row.put("auto", nz(r.get("remark")).startsWith(AUTO_TAG));
            row.put("source", nz(r.get("source")));
            row.put("batchId", nz(r.get("batch_id")));
            bump(st, status);
            bump(sv, nz(r.get("severity")));
            bump(ty, nz(r.get("def_type")));
            bump(ow, nz(r.get("owner")));
            bump(sr, sourceLabel(nz(r.get("source"))));
            out.add(row);
        }

        Map<String, Object> res = new LinkedHashMap<>();
        res.put("ok", true);
        res.put("total", out.size());
        res.put("byStatus", pairs(st));
        res.put("bySeverity", pairs(sv));
        res.put("byType", pairs(ty));
        res.put("byOwner", pairs(ow));
        res.put("bySource", pairs(sr));
        res.put("rows", out);
        res.put("sheet", "defect (DB)");
        res.put("sheetUrl", "");
        res.put("updatedAt", LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")));
        return res;
    }

    public List<String> statuses() {
        return jdbc.queryForList(
                "SELECT DISTINCT status FROM defect WHERE status IS NOT NULL AND status <> '' ORDER BY status",
                String.class);
    }

    // ── CRUD ────────────────────────────────────────────────────────────────

    @Transactional
    public Map<String, Object> create(Map<String, Object> p) {
        String id = nz(p.get("defectId"));
        if (id.isEmpty()) id = nextId();
        if (exists(id)) return Map.of("ok", false, "error", "이미 있는 결함ID입니다: " + id);

        String now = LocalDateTime.now().format(TS);
        jdbc.update("""
                INSERT INTO defect (defect_id, reg_dt, wbs_id, req_id, system_name, screen, def_type, severity,
                                    priority, content, repro, finder, owner, status, action, done_dt, retest,
                                    remark, auto_hash, source, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                id,
                orDefault(p.get("regDt"), LocalDate.now().format(YMD)),
                nz(p.get("wbsId")), nz(p.get("reqId")), nz(p.get("systemName")), nz(p.get("screen")),
                orDefault(p.get("defType"), DEF_TYPE), orDefault(p.get("severity"), DEF_SEV),
                orDefault(p.get("priority"), DEF_PRIO),
                nz(p.get("content")), nz(p.get("repro")), nz(p.get("finder")), nz(p.get("owner")),
                orDefault(p.get("status"), ST_OTHER), nz(p.get("action")), nz(p.get("doneDt")),
                nz(p.get("retest")), nz(p.get("remark")), null, "manual", now, now);
        return Map.of("ok", true, "defectId", id);
    }

    @Transactional
    public Map<String, Object> update(String id, Map<String, Object> p) {
        if (!exists(id)) return Map.of("ok", false, "error", "없는 결함ID입니다: " + id);

        Map<String, String> fields = new LinkedHashMap<>();
        fields.put("regDt", "reg_dt");
        fields.put("wbsId", "wbs_id");
        fields.put("reqId", "req_id");
        fields.put("systemName", "system_name");
        fields.put("screen", "screen");
        fields.put("defType", "def_type");
        fields.put("severity", "severity");
        fields.put("priority", "priority");
        fields.put("content", "content");
        fields.put("repro", "repro");
        fields.put("finder", "finder");
        fields.put("owner", "owner");
        fields.put("status", "status");
        fields.put("action", "action");
        fields.put("doneDt", "done_dt");
        fields.put("retest", "retest");
        fields.put("remark", "remark");

        List<String> sets = new ArrayList<>();
        List<Object> args = new ArrayList<>();
        fields.forEach((key, col) -> {
            if (p.containsKey(key)) {
                sets.add(col + " = ?");
                args.add(nz(p.get(key)));
            }
        });
        if (sets.isEmpty()) return Map.of("ok", false, "error", "변경할 항목이 없습니다.");

        sets.add("updated_at = ?");
        args.add(LocalDateTime.now().format(TS));
        args.add(id);
        jdbc.update("UPDATE defect SET " + String.join(", ", sets) + " WHERE defect_id = ?", args.toArray());
        return Map.of("ok", true, "defectId", id);
    }

    @Transactional
    public Map<String, Object> delete(String id) {
        int n = jdbc.update("DELETE FROM defect WHERE defect_id = ?", id);
        return n > 0 ? Map.of("ok", true, "deleted", id)
                : Map.of("ok", false, "error", "없는 결함ID입니다: " + id);
    }

    // ── IA 기획 피드백 이벤트 → 결함 자동 등록 ────────────────────────────────

    /**
     * 원본 syncPlanFeedbackToDefects() 이관.
     * @param dryRun true면 등록하지 않고 대상만 돌려준다
     */
    @Transactional
    public Map<String, Object> syncFromIa(boolean dryRun) {
        List<Map<String, Object>> screens = ia.rows();

        // 화면별 개발완료 상태 (자동수집 건의 상태를 IA에 맞춘다)
        Map<String, String> devByKey = new LinkedHashMap<>();
        List<Map<String, Object>> targets = new ArrayList<>();

        for (Map<String, Object> r : screens) {
            String id = nz(r.get("screen_id"));
            String cls = IaScopeService.classify(nz(r.get("status")), nz(r.get("remark")));
            devByKey.put(id, "done".equals(cls) ? ST_DONE : ST_OTHER);

            if (!"planfb".equals(IaScopeService.classifyPlan(nz(r.get("plan_status"))))) continue;
            String[] np = IaScopeService.splitNote(nz(r.get("plan_note")));
            if (np[0].isEmpty() && np[1].isEmpty()) continue;   // 기록할 내용 자체가 없음

            List<String> path = new ArrayList<>();
            for (String k : List.of("d1", "d2", "d3", "d4", "d5")) {
                String v = nz(r.get(k));
                if (!v.isEmpty()) path.add(v);
            }
            Map<String, Object> t = new LinkedHashMap<>();
            t.put("key", id);
            t.put("screen", String.join(" > ", path));
            t.put("owner", nz(r.get("owner")));
            t.put("dev", np[0]);
            t.put("plan", np[1]);
            targets.add(t);
        }

        // 화면별 마지막 기록 해시 (같은 내용 재등록 차단)
        Map<String, String> lastHash = new LinkedHashMap<>();
        for (Map<String, Object> d : jdbc.queryForList(
                "SELECT req_id, auto_hash, remark, defect_id FROM defect WHERE req_id IS NOT NULL AND req_id <> '' ORDER BY defect_id")) {
            String key = nz(d.get("req_id"));
            String h = nz(d.get("auto_hash"));
            if (h.isEmpty()) h = hashOf(nz(d.get("remark")));
            if (!key.isEmpty()) lastHash.put(key, h);
        }

        List<String> added = new ArrayList<>();
        int seq = maxSeq();
        String prefix = "DF-" + LocalDate.now().getYear() + "-";
        String now = LocalDateTime.now().format(TS);

        for (Map<String, Object> t : targets) {
            String key = nz(t.get("key"));
            String hash = hash(nz(t.get("plan")) + " " + nz(t.get("dev")));
            if (hash.equals(lastHash.get(key))) continue;      // 내용 그대로 → 추가 안 함

            String id = prefix + String.format("%03d", ++seq);
            if (!dryRun) {
                jdbc.update("""
                        INSERT INTO defect (defect_id, reg_dt, wbs_id, req_id, system_name, screen, def_type, severity,
                                            priority, content, repro, finder, owner, status, action, done_dt, retest,
                                            remark, auto_hash, source, created_at, updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        id, LocalDate.now().format(YMD), "", key, "", nz(t.get("screen")),
                        DEF_TYPE, DEF_SEV, DEF_PRIO, nz(t.get("plan")), "", "기획", nz(t.get("owner")),
                        devByKey.getOrDefault(key, ST_OTHER), nz(t.get("dev")), "", "",
                        AUTO_TAG + " #" + hash, hash, "ia-event", now, now);
            }
            added.add(id);
        }

        int synced = dryRun ? 0 : syncAutoStatus(devByKey);

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ok", true);
        out.put("dryRun", dryRun);
        out.put("planfb", targets.size());
        out.put("added", added.size());
        out.put("ids", added);
        out.put("statusSynced", synced);
        return out;
    }

    /** 자동수집 건의 상태를 IA 개발완료여부에 맞춘다 (원본 iafbSyncStatus_) */
    private int syncAutoStatus(Map<String, String> devByKey) {
        int changed = 0;
        for (Map<String, Object> d : jdbc.queryForList(
                "SELECT defect_id, req_id, status FROM defect WHERE source = 'ia-event'")) {
            String want = devByKey.get(nz(d.get("req_id")));
            if (want == null || want.equals(nz(d.get("status")))) continue;
            jdbc.update("UPDATE defect SET status = ?, updated_at = ? WHERE defect_id = ?",
                    want, LocalDateTime.now().format(TS), nz(d.get("defect_id")));
            changed++;
        }
        return changed;
    }

    // ── 헬퍼 ────────────────────────────────────────────────────────────────

    private boolean exists(String id) {
        Integer n = jdbc.queryForObject("SELECT COUNT(*) FROM defect WHERE defect_id = ?", Integer.class, id);
        return n != null && n > 0;
    }

    private int maxSeq() {
        int max = 0;
        for (String id : jdbc.queryForList("SELECT defect_id FROM defect", String.class)) {
            Matcher m = Pattern.compile("^DF-\\d{4}-(\\d+)$").matcher(nz(id));
            if (m.matches()) max = Math.max(max, Integer.parseInt(m.group(1)));
        }
        return max;
    }

    private String nextId() {
        return "DF-" + LocalDate.now().getYear() + "-" + String.format("%03d", maxSeq() + 1);
    }

    /** 비고에 붙은 자동수집 해시 추출 (없으면 빈 문자열) */
    static String hashOf(String remark) {
        Matcher m = HASH_TAG.matcher(nz(remark));
        return m.find() ? m.group(1) : "";
    }

    /** 원본 iafbHash_ — MD5 base64url 앞 10자 */
    static String hash(String raw) {
        try {
            byte[] d = MessageDigest.getInstance("MD5").digest(raw.getBytes(StandardCharsets.UTF_8));
            return Base64.getUrlEncoder().withoutPadding().encodeToString(d).substring(0, 10);
        } catch (Exception e) {
            return Integer.toHexString(raw.hashCode());
        }
    }

    private static void bump(Map<String, Integer> m, String k) {
        m.merge(k == null || k.isBlank() ? "(미기재)" : k, 1, Integer::sum);
    }

    private static List<Map<String, Object>> pairs(Map<String, Integer> m) {
        List<Map<String, Object>> out = new ArrayList<>();
        m.entrySet().stream()
                .sorted((a, b) -> b.getValue() - a.getValue())
                .forEach(e -> out.add(Map.of("name", e.getKey(), "n", e.getValue())));
        return out;
    }

    /** 화면 표시용 출처 라벨 — 엑셀로 들어온 건과 화면 등록분을 구분해 보여준다 */
    public static String sourceLabel(String source) {
        return switch (source == null ? "" : source) {
            case "excel" -> "엑셀 업로드";
            case "ia-event" -> "IA 이벤트";
            case "manual" -> "화면 등록";
            default -> "(미상)";
        };
    }

    private static String nz(Object v) { return v == null ? "" : String.valueOf(v).trim(); }

    private static String orDefault(Object v, String def) {
        String s = nz(v);
        return s.isEmpty() ? def : s;
    }
}
