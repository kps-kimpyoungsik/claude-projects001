package com.aegis.pm.unittest;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/**
 * IA 개발완료 범위 현황 — 원본 `getIaScopeJson()` / `setIaStatus()` 를 DB 기준으로 이관.
 * 응답 구조(키 이름·중첩)를 원본과 1:1로 맞춰 원본 화면(IaScope.html)을 그대로 쓴다.
 */
@Service
public class IaScopeService {

    private static final List<String> PLAN_KEYS = List.of("pdone", "devfb", "planfb", "feedback", "review", "pwait", "etc");
    private static final List<String> PLAN_OPTIONS = List.of("대기", "검토중", "개발 피드백", "기획 피드백", "기획완료");
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    private final JdbcTemplate jdbc;

    public IaScopeService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** 개발완료여부(자유서술) → 5분류. 원본 iaClassify_ 그대로 */
    static String classify(String status, String remark) {
        String s = nz(status), r = nz(remark);
        if (s.isEmpty()) return r.contains("대기") ? "wait" : "etc";
        if (s.contains("제외")) return "excl";
        if (s.contains("완료")) return "done";
        if (s.contains("대기") || s.contains("보류") || s.contains("예정")) return "wait";
        return "prog";
    }

    /** 기획검토상태 → 분류. 원본 iaClassifyPlan_ 그대로 */
    static String classifyPlan(String v) {
        String s = nz(v);
        if (s.isEmpty()) return "etc";
        if (s.contains("완료")) return "pdone";
        if (s.contains("피드백")) {
            if (s.contains("개발")) return "devfb";
            if (s.contains("기획")) return "planfb";
            return "feedback";
        }
        if (s.contains("검토")) return "review";
        if (s.contains("대기")) return "pwait";
        return "etc";
    }

    /** 검토내용 = "개발 -> 기획" 합성 문자열 (원본 iaSplitNote_) */
    static String[] splitNote(String v) {
        String s = nz(v);
        int i = s.indexOf("->");
        if (i < 0) return new String[]{"", s};
        return new String[]{s.substring(0, i).trim(), s.substring(i + 2).trim()};
    }

    static String joinNote(String dev, String plan) {
        String d = nz(dev), p = nz(plan);
        if (d.isEmpty() && p.isEmpty()) return "";
        return (d + " -> " + p).trim();
    }

    public List<Map<String, Object>> rows() {
        return jdbc.queryForList("""
                SELECT seq, screen_id, d1, d2, d3, d4, d5, scr_type, note, owner, status, remark, plan_status, plan_note
                  FROM ia_screen ORDER BY seq
                """);
    }

    /** 원본 getIaScopeJson() 형태 그대로 */
    public Map<String, Object> scope() {
        List<Map<String, Object>> rows = rows();

        Map<String, Area> areas = new LinkedHashMap<>();
        Map<String, Integer> overall = emptyCnt(), oPlan = emptyPlan();
        TreeSet<String> statusSeen = new TreeSet<>(), planSeen = new TreeSet<>();

        for (Map<String, Object> r : rows) {
            String d1 = s(r, "d1"), d2 = s(r, "d2"), d3 = s(r, "d3"), d4 = s(r, "d4"), d5 = s(r, "d5");
            String owner = s(r, "owner").isEmpty() ? "미지정" : s(r, "owner");
            String status = s(r, "status"), remark = s(r, "remark");
            String plan = s(r, "plan_status"), pnote = s(r, "plan_note");
            String cls = classify(status, remark);
            String pcls = classifyPlan(plan);
            if (!status.isEmpty()) statusSeen.add(status);
            if (!plan.isEmpty()) planSeen.add(plan);

            Area area = areas.computeIfAbsent(d1, Area::new);
            area.owners.add(owner);

            List<String> pathArr = new ArrayList<>();
            for (String p : List.of(d1, d2, d3)) if (!p.isEmpty()) pathArr.add(p);
            String ckey = String.join(" > ", pathArr);

            Card card = area.cards.computeIfAbsent(ckey, k -> {
                Card c = new Card();
                c.key = k; c.area = d1; c.d2 = d2; c.d3 = d3;
                c.title = !d3.isEmpty() ? d3 : (!d2.isEmpty() ? d2 : d1);
                c.path = pathArr;
                return c;
            });
            card.owners.add(owner);
            add(card.cnt, cls); add(area.cnt, cls); add(overall, cls);
            add(card.pcnt, pcls); add(area.pcnt, pcls); add(oPlan, pcls);

            String sk = d2.isEmpty() ? "(구분없음)" : d2;
            area.subs.computeIfAbsent(sk, k -> emptyCnt());
            area.subPlan.computeIfAbsent(sk, k -> emptyPlan());
            area.subOwners.computeIfAbsent(sk, k -> new LinkedHashSet<>()).add(owner);
            add(area.subs.get(sk), cls);
            add(area.subPlan.get(sk), pcls);

            String[] np = splitNote(pnote);
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("row", ((Number) r.get("seq")).intValue());   // DB seq — setIaStatus 대상 식별자
            item.put("id", s(r, "screen_id"));
            item.put("d4", d4);
            item.put("d5", d5);
            item.put("plan", plan);
            item.put("pcls", pcls);
            item.put("pnote", pnote);
            item.put("pnoteDev", np[0]);
            item.put("pnotePlan", np[1]);
            item.put("leaf", firstNonEmpty(d5, d4, d3, d2, d1));
            item.put("type", s(r, "scr_type"));
            item.put("owner", owner);
            item.put("status", status);
            item.put("cls", cls);
            item.put("note", s(r, "note"));
            item.put("remark", remark);
            card.items.add(item);

            if ("excl".equals(cls)) {
                Map<String, Object> ex = new LinkedHashMap<>();
                ex.put("name", firstNonEmpty(d5, d4, d3, d2, d1));
                ex.put("reason", !remark.isEmpty() ? remark : (!status.isEmpty() ? status : "사유 미기재"));
                card.excluded.add(ex);
            }
        }

        List<Map<String, Object>> areaList = new ArrayList<>();
        for (Area a : areas.values()) {
            Map<String, Object> am = new LinkedHashMap<>();
            am.put("name", a.name);
            am.put("cnt", a.cnt);
            am.put("pct", pct(a.cnt));
            am.put("pcnt", a.pcnt);
            am.put("ppct", planPct(a.pcnt));
            am.put("owners", new ArrayList<>(a.owners));

            List<Map<String, Object>> subs = new ArrayList<>();
            for (String sk : a.subs.keySet()) {
                Map<String, Object> sm = new LinkedHashMap<>();
                sm.put("name", sk);
                sm.put("cnt", a.subs.get(sk));
                sm.put("pct", pct(a.subs.get(sk)));
                sm.put("pcnt", a.subPlan.get(sk));
                sm.put("ppct", planPct(a.subPlan.get(sk)));
                sm.put("owners", new ArrayList<>(a.subOwners.get(sk)));
                subs.add(sm);
            }
            am.put("subs", subs);

            List<Map<String, Object>> cards = new ArrayList<>();
            for (Card c : a.cards.values()) cards.add(c.toMap());
            am.put("cards", cards);
            areaList.add(am);
        }

        List<String> planOptions = new ArrayList<>(PLAN_OPTIONS);
        for (String p : planSeen) if (!planOptions.contains(p)) planOptions.add(p);

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ok", true);
        out.put("rows", rows.size());
        out.put("sheet", "ia_screen (DB)");
        out.put("hasPlan", true);
        out.put("statusOptions", new ArrayList<>(statusSeen));
        out.put("planOptions", planOptions);
        out.put("sheetUrl", "");                 // DB 기준이라 외부 시트 링크 없음
        out.put("updatedAt", LocalDateTime.now().format(TS));
        out.put("overall", overall);
        out.put("overallPct", pct(overall));
        out.put("overallPlan", oPlan);
        out.put("overallPlanPct", planPct(oPlan));
        out.put("areas", areaList);
        return out;
    }

    /**
     * 원본 setIaStatus() 이관 — 화면에서 바꾼 값을 DB에 되쓴다.
     * row(=DB seq)와 id(Screen ID)를 함께 검증해 엉뚱한 행을 덮어쓰는 사고를 막는다.
     */
    public Map<String, Object> setStatus(Map<String, Object> p) {
        Integer seq = p.get("row") == null ? null : Integer.valueOf(String.valueOf(p.get("row")));
        String id = nz(p.get("id"));
        if (seq == null || id.isEmpty()) throw new IllegalArgumentException("row/id 누락");

        List<Map<String, Object>> cur = jdbc.queryForList(
                "SELECT screen_id, plan_note FROM ia_screen WHERE seq = ?", seq);
        if (cur.isEmpty()) throw new IllegalStateException("행을 찾을 수 없습니다(seq " + seq + ")");
        String idInDb = nz(cur.get(0).get("screen_id"));
        if (!idInDb.equals(id)) {
            throw new IllegalStateException("데이터가 변경되었습니다(행 " + seq + " = " + idInDb + "). 새로고침 후 다시 시도하세요.");
        }

        List<String> sets = new ArrayList<>();
        List<Object> args = new ArrayList<>();
        if (p.get("status") != null) { sets.add("status = ?"); args.add(nz(p.get("status"))); }
        if (p.get("remark") != null) { sets.add("remark = ?"); args.add(nz(p.get("remark"))); }
        if (p.get("plan") != null) { sets.add("plan_status = ?"); args.add(nz(p.get("plan"))); }

        if (p.get("pnote") != null) {
            sets.add("plan_note = ?");
            args.add(nz(p.get("pnote")));
        } else if (p.get("pnoteDev") != null || p.get("pnotePlan") != null) {
            // 한쪽만 수정해도 반대편 내용이 지워지지 않도록 현재 값을 읽어 합성한다
            String[] now = splitNote(nz(cur.get(0).get("plan_note")));
            String dev = p.get("pnoteDev") != null ? nz(p.get("pnoteDev")) : now[0];
            String plan = p.get("pnotePlan") != null ? nz(p.get("pnotePlan")) : now[1];
            sets.add("plan_note = ?");
            args.add(joinNote(dev, plan));
        }

        if (!sets.isEmpty()) {
            sets.add("updated_at = ?");
            args.add(LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
            args.add(seq);
            jdbc.update("UPDATE ia_screen SET " + String.join(", ", sets) + " WHERE seq = ?", args.toArray());
        }
        return scope();
    }

    // ── 집계 헬퍼 (원본 iaEmptyCnt_ / iaAdd_ / iaPct_ 그대로) ────────────────────

    private static Map<String, Integer> emptyCnt() {
        Map<String, Integer> m = new LinkedHashMap<>();
        for (String k : List.of("done", "prog", "wait", "etc", "excl", "total")) m.put(k, 0);
        return m;
    }

    private static Map<String, Integer> emptyPlan() {
        Map<String, Integer> m = new LinkedHashMap<>();
        m.put("total", 0);
        for (String k : PLAN_KEYS) m.put(k, 0);
        return m;
    }

    private static void add(Map<String, Integer> c, String cls) {
        c.merge(cls, 1, Integer::sum);
        c.merge("total", 1, Integer::sum);
    }

    /** 제외(excl)는 모수에서 뺀다 — 진척 왜곡 방지 */
    private static Map<String, Object> pct(Map<String, Integer> c) {
        int base = c.getOrDefault("total", 0) - c.getOrDefault("excl", 0);
        Map<String, Object> o = new LinkedHashMap<>();
        for (String k : List.of("done", "prog", "wait", "etc")) {
            o.put(k, base <= 0 ? 0d : Math.round(c.getOrDefault(k, 0) * 1000d / base) / 10d);
        }
        o.put("base", Math.max(base, 0));
        return o;
    }

    private static Map<String, Object> planPct(Map<String, Integer> c) {
        int total = c.getOrDefault("total", 0);
        Map<String, Object> o = new LinkedHashMap<>();
        o.put("base", total);
        for (String k : PLAN_KEYS) {
            o.put(k, total == 0 ? 0d : Math.round(c.getOrDefault(k, 0) * 1000d / total) / 10d);
        }
        return o;
    }

    private static String s(Map<String, Object> r, String k) { return nz(r.get(k)); }

    private static String nz(Object v) { return v == null ? "" : String.valueOf(v).trim(); }

    private static String firstNonEmpty(String... vs) {
        for (String v : vs) if (v != null && !v.isEmpty()) return v;
        return "";
    }

    private static class Area {
        final String name;
        final Map<String, Integer> cnt = emptyCnt();
        final Map<String, Integer> pcnt = emptyPlan();
        final LinkedHashSet<String> owners = new LinkedHashSet<>();
        final Map<String, Card> cards = new LinkedHashMap<>();
        final Map<String, Map<String, Integer>> subs = new LinkedHashMap<>();
        final Map<String, Map<String, Integer>> subPlan = new LinkedHashMap<>();
        final Map<String, LinkedHashSet<String>> subOwners = new LinkedHashMap<>();

        Area(String name) { this.name = name; }
    }

    private static class Card {
        String key, area, d2, d3, title;
        List<String> path = new ArrayList<>();
        final LinkedHashSet<String> owners = new LinkedHashSet<>();
        final Map<String, Integer> cnt = emptyCnt();
        final Map<String, Integer> pcnt = emptyPlan();
        final List<Map<String, Object>> items = new ArrayList<>();
        final List<Map<String, Object>> excluded = new ArrayList<>();

        Map<String, Object> toMap() {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("key", key);
            m.put("area", area);
            m.put("d2", d2);
            m.put("d3", d3);
            m.put("title", title);
            m.put("path", path);
            m.put("owners", new ArrayList<>(owners));
            m.put("cnt", cnt);
            m.put("pct", pct(cnt));
            m.put("pcnt", pcnt);
            m.put("ppct", planPct(pcnt));
            m.put("items", items);
            m.put("excluded", excluded);
            return m;
        }
    }
}
