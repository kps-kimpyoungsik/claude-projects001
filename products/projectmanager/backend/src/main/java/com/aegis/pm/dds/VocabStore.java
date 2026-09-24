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
 * 어휘 사전 저장·조회 계층 (05 §4·§5·§6).
 *
 * <p>세 가지를 한 곳에서 한다: 용어 CRUD · 3단 매칭 · 진화 신호 수집.
 * 매칭과 진화를 붙여 둔 이유는 매칭 실패 그 자체가 진화 신호이기 때문이다 —
 * 떼어 놓으면 "실패했는데 아무도 기록하지 않는" 경로가 생긴다.
 */
@Service
public class VocabStore {

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    /** 미매칭 토큰이 몇 번 나와야 LOCAL draft 후보가 되는가 (05 §5.1) */
    static final int MISS_TO_DRAFT = 3;

    /** 사용 횟수만으로 공통 승격을 제안하는 하한 (05 §5.1 — 제안일 뿐 자동 승격 아님) */
    static final int PROMOTE_USAGE = 5;

    private final JdbcTemplate jdbc;

    public VocabStore(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    // ── 조회 ────────────────────────────────────────────────────────────────

    public List<Map<String, Object>> terms(String level, String kind, String q) {
        StringBuilder sql = new StringBuilder("SELECT * FROM vocab_term WHERE 1=1");
        List<Object> args = new ArrayList<>();
        if (level != null && !level.isBlank()) { sql.append(" AND level = ?"); args.add(level); }
        if (kind != null && !kind.isBlank()) { sql.append(" AND kind = ?"); args.add(kind); }
        if (q != null && !q.isBlank()) {
            sql.append(" AND (LOWER(term) LIKE ? OR LOWER(synonyms) LIKE ?)");
            String like = "%" + q.toLowerCase() + "%";
            args.add(like);
            args.add(like);
        }
        sql.append(" ORDER BY level, kind, term");
        return lower(jdbc.queryForList(sql.toString(), args.toArray()));
    }

    public Map<String, Object> term(String termId) {
        return lower(jdbc.queryForMap("SELECT * FROM vocab_term WHERE term_id = ?", termId));
    }

    public List<Map<String, Object>> history(String termId) {
        return lower(jdbc.queryForList("SELECT * FROM vocab_history WHERE term_id = ? ORDER BY version DESC", termId));
    }

    /** 아직 사전에 없는 토큰들 — 무엇을 더 채워야 하는지의 목록 */
    public List<Map<String, Object>> misses(int minHits) {
        return lower(jdbc.queryForList(
                "SELECT * FROM vocab_miss WHERE hits >= ? ORDER BY hits DESC, last_at DESC", minHits));
    }

    /** 이 표기의 용어가 이미 있는가 — 재시드가 계층을 건드리지 않기 위한 확인 */
    public boolean exists(String term, String domain) {
        return findId(term, domain) != null;
    }

    /**
     * 공통(STD)으로 올릴 근거가 쌓인 용어 — <b>제안만 한다</b>(05 ADR V5).
     *
     * <p>표준은 합의다. 빈도는 합의의 근거일 뿐 합의 자체가 아니므로 시스템이 올리지 않는다.
     * 근거 두 갈래: 여러 표에 같은 헤더로 나타났거나(공통성), 매칭에 실제로 많이 쓰였거나(사용).
     */
    public List<Map<String, Object>> promotions() {
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> t : lower(jdbc.queryForList(
                "SELECT * FROM vocab_term WHERE level <> 'STD' AND status <> 'deprecated'"))) {
            int inDatasets = datasetHits(String.valueOf(t.get("term")));
            int used = t.get("usage_count") == null ? 0 : ((Number) t.get("usage_count")).intValue();
            List<String> why = new ArrayList<>();
            if (inDatasets >= 2) why.add("표 " + inDatasets + "개에 같은 헤더로 존재");
            if (used >= PROMOTE_USAGE) why.add("매칭에 " + used + "회 사용");
            if (why.isEmpty()) continue;
            t.put("in_datasets", inDatasets);
            t.put("suggest_level", "STD");
            t.put("why", String.join(" · ", why));
            out.add(t);
        }
        out.sort((a, b) -> ((Number) b.get("in_datasets")).intValue() - ((Number) a.get("in_datasets")).intValue());
        return out;
    }

    private int datasetHits(String term) {
        try {
            Integer n = jdbc.queryForObject(
                    "SELECT COUNT(DISTINCT dataset_id) FROM dataset_column WHERE name = ?", Integer.class, term);
            return n == null ? 0 : n;
        } catch (org.springframework.dao.DataAccessException e) {
            return 0;   // dataset_column 이 없는 환경에서도 사전은 동작해야 한다
        }
    }

    /**
     * 중복 후보 — 같은 원천을 공유하는 표기 묶음 (T115 SSI §3-⑤).
     *
     * <p><b>합치지 않는다.</b> 같은 표기라도 도메인이 다르면 뜻이 다를 수 있으므로 시스템은
     * "이것들이 같은 원천을 가리키는 것 같다"까지만 말하고, 병합은 사람이 결정한다.
     * 묶음이 있는데 이 목록에 안 뜨면 침묵 드롭이다(T108 NSP-9).
     */
    public List<Map<String, Object>> duplicates() {
        Map<String, List<Map<String, Object>>> bySource = new java.util.LinkedHashMap<>();
        for (Map<String, Object> t : lower(jdbc.queryForList(
                "SELECT * FROM vocab_term WHERE status <> 'deprecated' AND kind <> 'code'"))) {
            String term = String.valueOf(t.get("term"));
            String src = t.get("related") != null && !String.valueOf(t.get("related")).isBlank()
                    ? String.valueOf(t.get("related"))
                    : Ingest.classify(term).source();
            if (src == null || src.equals(term)) continue;   // 원천 자신은 묶음의 대상이 아니다
            bySource.computeIfAbsent(src, k -> new ArrayList<>()).add(t);
        }

        List<Map<String, Object>> out = new ArrayList<>();
        bySource.forEach((src, members) -> {
            if (members.size() < 2) return;   // 혼자면 중복이 아니다
            Map<String, Object> g = new java.util.LinkedHashMap<>();
            g.put("source", src);
            g.put("source_registered", exists(src, null));
            g.put("count", members.size());
            g.put("terms", members.stream().map(m -> m.get("term")).toList());
            g.put("decision", "사람 판정 필요 — 뜻이 같으면 동의어 흡수, 다르면 원천 아래 파생으로 유지");
            out.add(g);
        });
        out.sort((a, b) -> ((Number) b.get("count")).intValue() - ((Number) a.get("count")).intValue());
        return out;
    }

    /** 이 원천을 가리키는 파생 용어들 — 표준 필드의 동의어 후보가 된다 (T115 SSI 계보) */
    public List<Map<String, Object>> derivedOf(String sourceTerm) {
        if (sourceTerm == null || sourceTerm.isBlank()) return List.of();
        return lower(jdbc.queryForList(
                "SELECT * FROM vocab_term WHERE related = ? AND status <> 'deprecated'", sourceTerm));
    }

    public List<Map<String, Object>> sources() {
        return lower(jdbc.queryForList("SELECT * FROM vocab_source ORDER BY absorbed_at DESC"));
    }

    // ── 매칭 (05 §6) ────────────────────────────────────────────────────────

    /**
     * 컬럼명·토큰 하나를 사전으로 해석한다. 성공하면 usage_count 가, 실패하면 vocab_miss 가
     * 는다 — 조회 자체가 진화 신호를 남긴다.
     *
     * @return 매칭된 용어 행 + matched_by(exact|synonym|normalized) + confidence, 실패 시 null
     */
    @Transactional
    public Map<String, Object> match(String token) {
        Map<String, Object> hit = find(token);
        if (token == null || token.isBlank()) return null;
        if (hit == null) {
            recordMiss(token.trim());
            return null;
        }
        jdbc.update("UPDATE vocab_term SET usage_count = usage_count + 1 WHERE term_id = ?", hit.get("term_id"));
        return hit;
    }

    /**
     * {@link #match} 와 같은 판정이되 <b>기록을 남기지 않는다</b> — 사용 횟수·미스 집계를 올리지 않는다.
     * 자격 게이트처럼 같은 헤더를 몇 번이고 다시 평가하는 곳에서 쓴다(재평가마다 통계가 부풀면 승격 판단이 틀어진다).
     */
    public Map<String, Object> peek(String token) {
        return find(token);
    }

    private Map<String, Object> find(String token) {
        if (token == null || token.isBlank()) return null;
        String t = token.trim();

        Map<String, Object> hit = first("SELECT * FROM vocab_term WHERE term = ? AND status <> 'deprecated'", t);
        String by = "exact";
        double conf = 1.0;

        if (hit == null) {
            // LIKE 는 후보를 넓힐 뿐이라 쉼표 단위로 정확히 재판정한다 (부분문자열 오매칭 차단)
            hit = first("SELECT * FROM vocab_term WHERE status <> 'deprecated' AND synonyms IS NOT NULL"
                    + " AND LOWER(synonyms) LIKE ?", "%" + t.toLowerCase() + "%");
            if (hit != null && !hasSynonym(String.valueOf(hit.get("synonyms")), t)) hit = null;
            by = "synonym";
            conf = 0.9;
        }
        if (hit == null) {
            String n = Absorb.norm(t);
            for (Map<String, Object> row : lower(jdbc.queryForList("SELECT * FROM vocab_term WHERE status <> 'deprecated'"))) {
                if (Absorb.norm(String.valueOf(row.get("term"))).equals(n)
                        || hasNormSynonym(String.valueOf(row.get("synonyms")), n)) {
                    hit = row;
                    break;
                }
            }
            by = "normalized";
            conf = 0.75;
        }

        if (hit == null) return null;
        hit.put("matched_by", by);
        hit.put("confidence", conf);
        return hit;
    }

    private static boolean hasSynonym(String synonyms, String token) {
        if (synonyms == null || "null".equals(synonyms)) return false;
        for (String s : synonyms.split(",")) {
            if (s.trim().equalsIgnoreCase(token.trim())) return true;
        }
        return false;
    }

    private static boolean hasNormSynonym(String synonyms, String normToken) {
        if (synonyms == null || "null".equals(synonyms)) return false;
        for (String s : synonyms.split(",")) {
            if (!s.isBlank() && Absorb.norm(s).equals(normToken)) return true;
        }
        return false;
    }

    // ── 진화 (05 §5) ────────────────────────────────────────────────────────

    /**
     * 미매칭 토큰 누적. MISS_TO_DRAFT 회부터 LOCAL draft 를 <b>후보로</b> 만든다.
     * 등재가 아니다 — status=draft 이고 definition 은 사람이 채워야 approved 가 된다.
     */
    @Transactional
    public void recordMiss(String token) {
        if (!Absorb.accepts(token)) return;   // 경계 밖 토큰은 진화 신호도 되지 않는다
        String now = now();
        int updated = jdbc.update("UPDATE vocab_miss SET hits = hits + 1, last_at = ? WHERE token = ?", now, token);
        if (updated == 0) {
            jdbc.update("INSERT INTO vocab_miss (token, hits, promoted, first_at, last_at) VALUES (?,1,FALSE,?,?)",
                    token, now, now);
            return;
        }
        Integer hits = jdbc.queryForObject("SELECT hits FROM vocab_miss WHERE token = ?", Integer.class, token);
        Boolean promoted = jdbc.queryForObject("SELECT promoted FROM vocab_miss WHERE token = ?", Boolean.class, token);
        if (hits != null && hits >= MISS_TO_DRAFT && !Boolean.TRUE.equals(promoted)) {
            Map<String, Object> draft = new LinkedHashMap<>();
            draft.put("level", "LOCAL");
            draft.put("kind", "attribute");
            draft.put("term", token);
            draft.put("definition", "(자동 초안) 업로드 데이터에서 " + hits + "회 관측된 미등재 용어");
            draft.put("source_id", VocabSeeder.SRC_EVOLUTION);
            draft.put("status", "draft");
            draft.put("confidence", 0.3);
            save(draft, "rule", "미매칭 " + hits + "회 누적");
            jdbc.update("UPDATE vocab_miss SET promoted = TRUE WHERE token = ?", token);
        }
    }

    // ── 쓰기 ────────────────────────────────────────────────────────────────

    /**
     * 신규 등록 또는 갱신. 기존 용어를 고치면 version 이 오르고 이력이 남는다(덮어쓰기 없음, 05 §5.2).
     * 같은 (term, domain) 이 이미 있으면 중복 생성하지 않고 그 건을 갱신한다.
     */
    @Transactional
    public String save(Map<String, Object> in, String decidedBy, String reason) {
        String term = str(in.get("term"));
        if (term == null || term.isBlank()) throw new IllegalArgumentException("term 은 필수입니다");
        String rejected = Absorb.rejectReason(term);
        if (rejected != null && !"human".equals(decidedBy)) {
            throw new IllegalArgumentException("흡수 경계 밖 토큰입니다: " + rejected);
        }
        String domain = str(in.get("domain"));
        String id = str(in.get("term_id"));
        if (id == null || id.isBlank()) id = findId(term, domain);
        String now = now();

        if (id == null) {
            id = "VT-" + Integer.toHexString((term + "|" + (domain == null ? "" : domain)).hashCode()).toUpperCase();
            // term_id 는 표기에서 나온 고정값이라, 정리됐다 다시 들어온 용어는 옛 이력과 같은 id 를 쓴다.
            // 버전을 1로 못박으면 그 이력과 충돌하므로 이력 체인을 이어 받는다 — 한 표기 = 한 줄기 이력.
            int first = nextVersion(id);
            jdbc.update("INSERT INTO vocab_term (term_id, level, kind, term, domain, definition, intent, source_id,"
                            + " synonyms, related, code_values, format_rule, axis, std_field,"
                            + " status, version, confidence, usage_count, miss_count, created_at, updated_at)"
                            + " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,?,?)",
                    id, def(in.get("level"), "LOCAL"), def(in.get("kind"), "attribute"), term, domain,
                    str(in.get("definition")), str(in.get("intent")), def(in.get("source_id"), VocabSeeder.SRC_HUMAN),
                    str(in.get("synonyms")), str(in.get("related")), str(in.get("code_values")),
                    str(in.get("format_rule")), str(in.get("axis")), str(in.get("std_field")),
                    def(in.get("status"), "draft"), first, num(in.get("confidence")), now, now);
            writeHistory(id, first, "create", null, term, reason, decidedBy, now);
            return id;
        }

        Map<String, Object> before = term(id);
        // human 이 정한 것은 자동 판정이 덮지 않는다 (05 §3.1 1순위)
        if (!"human".equals(decidedBy) && VocabSeeder.SRC_HUMAN.equals(before.get("source_id"))) return id;

        int version = nextVersion(id);
        Object conf = num(in.get("confidence")) == null ? before.get("confidence") : num(in.get("confidence"));
        jdbc.update("UPDATE vocab_term SET level=?, kind=?, domain=?, definition=?, intent=?, source_id=?,"
                        + " synonyms=?, related=?, code_values=?, format_rule=?, axis=?, std_field=?,"
                        + " status=?, version=?, confidence=?, updated_at=? WHERE term_id=?",
                def(in.get("level"), str(before.get("level"))), def(in.get("kind"), str(before.get("kind"))),
                def(in.get("domain"), str(before.get("domain"))), def(in.get("definition"), str(before.get("definition"))),
                def(in.get("intent"), str(before.get("intent"))), def(in.get("source_id"), str(before.get("source_id"))),
                def(in.get("synonyms"), str(before.get("synonyms"))), def(in.get("related"), str(before.get("related"))),
                def(in.get("code_values"), str(before.get("code_values"))),
                def(in.get("format_rule"), str(before.get("format_rule"))), def(in.get("axis"), str(before.get("axis"))),
                def(in.get("std_field"), str(before.get("std_field"))), def(in.get("status"), str(before.get("status"))),
                version, conf, now, id);
        writeHistory(id, version, changeKind(before, in), str(before.get("definition")),
                str(in.get("definition")), reason, decidedBy, now);
        return id;
    }

    /** 이 용어 표기의 다음 이력 버전 — 과거 이력이 있으면 그 뒤를 잇는다 */
    private int nextVersion(String termId) {
        Integer v = jdbc.queryForObject(
                "SELECT COALESCE(MAX(version), 0) FROM vocab_history WHERE term_id = ?", Integer.class, termId);
        return (v == null ? 0 : v) + 1;
    }

    private String findId(String term, String domain) {
        List<String> ids = domain == null
                ? jdbc.queryForList("SELECT term_id FROM vocab_term WHERE term = ? AND domain IS NULL",
                        String.class, term)
                : jdbc.queryForList("SELECT term_id FROM vocab_term WHERE term = ? AND domain = ?",
                        String.class, term, domain);
        return ids.isEmpty() ? null : ids.get(0);
    }

    private static String changeKind(Map<String, Object> before, Map<String, Object> in) {
        if ("deprecated".equals(in.get("status"))) return "deprecate";
        if (in.get("code_values") != null) return "code";
        if (in.get("synonyms") != null) return "synonym";
        if (in.get("level") != null && !in.get("level").equals(before.get("level"))) return "promote";
        return "definition";
    }

    private void writeHistory(String id, int version, String kind, String beforeVal, String afterVal,
                              String reason, String by, String at) {
        jdbc.update("INSERT INTO vocab_history (term_id, version, change_kind, before_val, after_val,"
                        + " reason, decided_by, changed_at) VALUES (?,?,?,?,?,?,?,?)",
                id, version, kind, cut(beforeVal, 2000), cut(afterVal, 2000),
                reason == null || reason.isBlank() ? "(사유 미기재)" : cut(reason, 500), by, at);
    }

    @Transactional
    public void source(String sourceId, String kind, String uri, String scopeIn, String scopeOut, int count) {
        jdbc.update("DELETE FROM vocab_source WHERE source_id = ?", sourceId);
        jdbc.update("INSERT INTO vocab_source (source_id, kind, uri, scope_in, scope_out, absorbed_at, term_count)"
                        + " VALUES (?,?,?,?,?,?,?)",
                sourceId, kind, cut(uri, 500), cut(scopeIn, 500), cut(scopeOut, 500), now(), count);
    }

    // ── 보조 ────────────────────────────────────────────────────────────────

    private Map<String, Object> first(String sql, Object... args) {
        List<Map<String, Object>> rows = jdbc.queryForList(sql, args);
        return rows.isEmpty() ? null : lower(rows.get(0));
    }

    /**
     * 컬럼 키를 소문자로 통일한다. H2 는 대문자(TERM_ID), PostgreSQL 은 소문자(term_id)로 주기
     * 때문에 그대로 내보내면 <b>같은 API 가 DB 종류에 따라 다른 키를 낸다</b>.
     */
    private static Map<String, Object> lower(Map<String, Object> row) {
        return Rows.lower(row);
    }

    private static List<Map<String, Object>> lower(List<Map<String, Object>> rows) {
        return Rows.lower(rows);
    }

    static String now() {
        return LocalDateTime.now().format(TS);
    }

    private static String str(Object o) {
        return o == null ? null : String.valueOf(o);
    }

    private static String def(Object o, String fallback) {
        String s = str(o);
        return s == null || s.isBlank() ? fallback : s;
    }

    private static Double num(Object o) {
        return o instanceof Number n ? n.doubleValue() : null;
    }

    private static String cut(String s, int max) {
        return s == null ? null : s.length() <= max ? s : s.substring(0, max);
    }
}
