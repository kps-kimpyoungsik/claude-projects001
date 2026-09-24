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
 * 표준 바인딩 엔진 — 들어온 표의 컬럼을 표준 필드에 붙이고, <b>붙인 결과로 학습한다</b>.
 *
 * <h3>학습이란 무엇인가 (이 클래스의 정의)</h3>
 * 신경망을 돌리는 것이 아니라 <b>관측이 쌓일수록 판정이 나아지는 것</b>이다. 지금 데이터
 * 규모(데이터셋 6개·헤더 40개)에서 신경망은 학습할 것이 없다 — 대신 아래 3층이 실제로 는다:
 *
 * <ol>
 *   <li><b>L0 규칙</b> — 어휘 사전 동의어 일치. 사전이 자라면 인식 범위가 는다(Phase 1)</li>
 *   <li><b>L1 통계</b> — 같은 표기가 어느 표준 필드에 몇 번 붙었는지({@code binding_feedback}).
 *       관측이 쌓이면 확신도가 오르고, 애매한 표기도 다수결로 갈린다</li>
 *   <li><b>L2 교정</b> — 사람이 고친 바인딩. <b>가중치가 가장 크고 자동 판정이 덮지 못한다.</b>
 *       한 번 고쳐 주면 그 표기는 다음부터 그 필드로 간다 — 이것이 가장 값싼 학습이다</li>
 * </ol>
 *
 * <p><b>임베딩은 아직 없다.</b> 조달되면 {@link #semanticScore}만 구현하면 끼워진다(T102 NTM
 * Port). 지금 넣지 않는 이유는 c-TF-IDF 로 충분한 규모이기 때문이고(00 연구조사 판정),
 * 모델 없이 자리만 만들어 두면 "있는 척"이 되기 때문이다.
 */
@Service
public class BindingEngine {

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    /** 이 비율 이상 붙으면 표준 인스턴스로 인정 (04 §2.2) */
    static final double BIND_STD = 0.7;
    /** 이 비율 이상이면 도메인 확장 후보 */
    static final double BIND_DOM = 0.4;
    /** 사람 교정 1건이 자동 관측 몇 건만큼의 무게를 갖는가 — 사람이 훨씬 무겁다 */
    static final int HUMAN_WEIGHT = 10;

    private final JdbcTemplate jdbc;
    private final VocabStore vocab;

    public BindingEngine(JdbcTemplate jdbc, VocabStore vocab) {
        this.jdbc = jdbc;
        this.vocab = vocab;
    }

    /** 한 컬럼의 바인딩 판정 결과 */
    public record Hit(String stdId, String fieldKey, double confidence, String source, String evidence) {}

    // ── 바인딩 ──────────────────────────────────────────────────────────────

    /**
     * 데이터셋 1개를 표준에 바인딩한다. 가장 많이 붙은 표준이 그 데이터셋의 표준이 된다.
     *
     * <p>매핑률이 낮다고 <b>거부하지 않는다</b> — 거부는 자격 게이트(Phase 4)의 일이고 여기는
     * "표준에 맞는가"만 본다. 표준에 없는 완전히 새로운 종류의 좋은 데이터가 있을 수 있다.
     */
    @Transactional
    public Map<String, Object> bind(String datasetId) {
        List<String> headers = jdbc.queryForList(
                "SELECT name FROM dataset_column WHERE dataset_id = ? ORDER BY col_no",
                String.class, datasetId);
        if (headers.isEmpty()) return result(datasetId, null, 0, 0, 0, "USR", "컬럼 없음");

        // 1패스 — 맥락 없이 해석해 이 표가 어느 표준 쪽인지 정한다
        Map<String, List<Object[]>> vote = new LinkedHashMap<>();
        for (String h : headers) {
            Hit hit = classify(h);
            if (hit != null) vote.computeIfAbsent(hit.stdId(), k -> new ArrayList<>()).add(new Object[]{h, hit});
        }
        String winner = vote.entrySet().stream()
                .max((a, b) -> a.getValue().size() - b.getValue().size())
                .map(Map.Entry::getKey).orElse(null);
        if (winner == null) return result(datasetId, null, headers.size(), 0, 0, "USR", "매칭 0건");

        // 2패스 — 정해진 표준을 맥락으로 주고 다시 해석한다. `담당자` 처럼 여러 표준에 있는
        // 표기가 이 표의 표준 쪽으로 제대로 붙는다(1패스만으로는 통계가 고른 다른 표준으로 갔다).
        Map<String, List<Object[]>> byStd = new LinkedHashMap<>();
        int matched = 0;
        for (String h : headers) {
            Hit hit = classify(h, winner);
            if (hit == null) continue;
            matched++;
            byStd.computeIfAbsent(hit.stdId(), k -> new ArrayList<>()).add(new Object[]{h, hit});
        }
        if (!byStd.containsKey(winner)) return result(datasetId, null, headers.size(), matched, 0, "USR", "매칭 0건");

        // 이긴 표준의 바인딩만 저장한다 — 여러 표준에 걸친 컬럼을 다 남기면 집계가 중복된다.
        // 단 **사람이 고친 것은 이긴 표준이 아니어도 지우지 않는다**: 재바인딩이 교정을
        // 버리면 L2 우선 원칙이 이 경로에서만 깨진다(실측으로 실제로 깨져 있었다).
        jdbc.update("DELETE FROM dataset_binding WHERE dataset_id = ? AND source <> 'human'", datasetId);
        List<String> keep = jdbc.queryForList(
                "SELECT col_name FROM dataset_binding WHERE dataset_id = ? AND source = 'human'",
                String.class, datasetId);
        String now = LocalDateTime.now().format(TS);
        for (Object[] pair : byStd.get(winner)) {
            String col = (String) pair[0];
            Hit hit = (Hit) pair[1];
            if (keep.contains(col)) continue;   // 사람이 고친 컬럼은 그대로 둔다
            jdbc.update("""
                    INSERT INTO dataset_binding (dataset_id, col_name, std_id, field_key,
                                                 confidence, source, evidence, bound_at)
                    VALUES (?,?,?,?,?,?,?,?)
                    """, datasetId, col, hit.stdId(), hit.fieldKey(),
                    hit.confidence(), hit.source(), hit.evidence(), now);
            learn(col, hit.stdId(), hit.fieldKey(), false);   // 관측을 학습에 남긴다
        }

        // 매핑률은 실제로 남은 바인딩 기준이다 — 사람이 다른 표준으로 고친 컬럼까지 포함해야
        // "이 표의 몇 %가 해석됐나"가 맞는 값이 된다
        Integer stored = jdbc.queryForObject(
                "SELECT COUNT(*) FROM dataset_binding WHERE dataset_id = ?", Integer.class, datasetId);
        int bound = stored == null ? byStd.get(winner).size() : stored;
        double ratio = (double) bound / headers.size();
        String level = ratio >= BIND_STD ? "STD" : ratio >= BIND_DOM ? "DOM" : "USR";
        jdbc.update("UPDATE dataset SET std_id = ?, bind_ratio = ?, ds_level = ? WHERE dataset_id = ?",
                ratio >= BIND_DOM ? winner : null, ratio, level, datasetId);

        return result(datasetId, ratio >= BIND_DOM ? winner : null, headers.size(), matched, bound,
                level, level.equals("STD") ? "표준 인스턴스"
                        : level.equals("DOM") ? "도메인 확장 후보 — 표준에 없는 컬럼이 남았다"
                        : "표준 바인딩 없음 — 새 종류일 수 있다");
    }

    /**
     * 컬럼 표기 하나를 표준 필드로 해석한다 — L2(사람) → L1(통계) → L0(규칙) 순.
     *
     * <p>순서가 중요하다. 사람이 고친 것을 규칙이 다시 덮으면 교정이 무의미해진다.
     */
    public Hit classify(String header) {
        return classify(header, null);
    }

    /**
     * 맥락(유력 표준)을 주고 해석한다.
     *
     * <p>`담당자`·`비고` 같은 표기는 <b>여러 표준에 정당하게 존재한다</b>(작업에도 담당자가 있고
     * 결함에도 있다). 맥락 없이 통계로 하나에 고정하면, 결함 표의 `담당자` 가 STD-TASK 로
     * 판정돼 그 표의 바인딩에서 버려진다 — 실측에서 실제로 그렇게 됐다.
     *
     * @param preferStdId 이 표준 안에 같은 표기가 있으면 그쪽을 먼저 본다 (null 이면 맥락 없음)
     */
    public Hit classify(String header, String preferStdId) {
        String norm = Absorb.norm(Ingest.nameOf(header));

        // 맥락이 있으면 그 표준 안에서 먼저 찾는다 — 통계·규칙보다 앞선다.
        // 사람 교정(L2)보다는 뒤다: 사람이 이 데이터셋에서 직접 지정한 것이 가장 강하다.
        if (preferStdId != null && !preferStdId.isBlank() && !hasHumanFor(norm)) {
            for (Map<String, Object> f : Rows.lower(jdbc.queryForList(
                    "SELECT std_id, field_key, label, synonyms FROM standard_field WHERE std_id = ?",
                    preferStdId))) {
                if (matchesSynonym(str(f.get("synonyms")), str(f.get("label")), norm)) {
                    return new Hit(preferStdId, str(f.get("field_key")), 0.9, "rule",
                            "이 표가 붙은 " + preferStdId + " 의 '" + f.get("label") + "' 와 일치");
                }
            }
        }
        return classifyGlobal(header, norm);
    }

    private boolean hasHumanFor(String norm) {
        Integer n = jdbc.queryForObject(
                "SELECT COUNT(*) FROM binding_feedback WHERE col_norm = ? AND human > 0", Integer.class, norm);
        return n != null && n > 0;
    }

    private Hit classifyGlobal(String header, String norm) {

        // L2 — 사람이 고친 적이 있으면 그것이 답이다 (자동 판정이 덮지 못한다)
        List<Map<String, Object>> human = jdbc.queryForList("""
                SELECT std_id, field_key, human FROM binding_feedback
                 WHERE col_norm = ? AND human > 0 ORDER BY human DESC
                """, norm);
        if (!human.isEmpty()) {
            Map<String, Object> r = Rows.lower(human.get(0));
            return new Hit(str(r.get("std_id")), str(r.get("field_key")), 1.0, "human",
                    "사람이 " + r.get("human") + "회 확정한 매핑");
        }

        // L1 — 관측 통계. 같은 표기가 반복해서 붙은 곳이 있으면 그쪽으로 기운다
        List<Map<String, Object>> stat = jdbc.queryForList("""
                SELECT std_id, field_key, hits FROM binding_feedback
                 WHERE col_norm = ? AND hits > 0 ORDER BY hits DESC
                """, norm);
        if (stat.size() == 1 || (stat.size() > 1 && hits(stat, 0) > hits(stat, 1))) {
            Map<String, Object> r = Rows.lower(stat.get(0));
            int n = ((Number) r.get("hits")).intValue();
            // 관측이 쌓일수록 확신이 오르되 1.0 에는 닿지 않는다 — 통계는 사람이 아니다
            double conf = Math.min(0.6 + n * 0.05, 0.95);
            return new Hit(str(r.get("std_id")), str(r.get("field_key")), conf, "stat",
                    "같은 표기가 " + n + "회 이 필드에 바인딩됨");
        }

        // L0 — 어휘 사전 기반 규칙. 사전이 자라면 여기가 함께 자란다
        for (Map<String, Object> f : jdbc.queryForList("""
                SELECT s.std_id, s.field_key, s.label, s.synonyms
                  FROM standard_field s JOIN standard_dataset d ON d.std_id = s.std_id
                 WHERE d.status <> 'deprecated'
                """)) {
            Map<String, Object> r = Rows.lower(f);
            if (!matchesSynonym(str(r.get("synonyms")), str(r.get("label")), norm)) continue;
            return new Hit(str(r.get("std_id")), str(r.get("field_key")), 0.9, "rule",
                    "표준 필드 '" + r.get("label") + "' 의 표기와 일치");
        }
        return null;
    }

    private static boolean matchesSynonym(String synonyms, String label, String norm) {
        if (Absorb.norm(label).equals(norm)) return true;
        if (synonyms == null || "null".equals(synonyms)) return false;
        for (String s : synonyms.split(",")) {
            if (!s.isBlank() && Absorb.norm(s).equals(norm)) return true;
        }
        return false;
    }

    // ── 학습 ────────────────────────────────────────────────────────────────

    /**
     * 관측·교정을 학습 기록에 남긴다. 이것이 다음 {@link #classify} 의 근거가 된다.
     *
     * @param human 사람이 확정·교정한 것인가 — true 면 자동 판정이 다시는 덮지 못한다
     */
    @Transactional
    public void learn(String colName, String stdId, String fieldKey, boolean human) {
        String norm = Absorb.norm(Ingest.nameOf(colName));
        String now = LocalDateTime.now().format(TS);
        int updated = jdbc.update("""
                UPDATE binding_feedback SET hits = hits + ?, human = human + ?, last_at = ?
                 WHERE col_norm = ? AND std_id = ? AND field_key = ?
                """, human ? HUMAN_WEIGHT : 1, human ? 1 : 0, now, norm, stdId, fieldKey);
        if (updated == 0) {
            jdbc.update("""
                    INSERT INTO binding_feedback (col_norm, std_id, field_key, hits, human, last_at)
                    VALUES (?,?,?,?,?,?)
                    """, norm, stdId, fieldKey, human ? HUMAN_WEIGHT : 1, human ? 1 : 0, now);
        }
    }

    /**
     * 사람이 바인딩을 고친다 — 학습의 가장 값싼 입력이다.
     * 고친 순간 그 표기는 다음 데이터셋에서도 같은 필드로 간다.
     */
    @Transactional
    public Map<String, Object> correct(String datasetId, String colName, String stdId, String fieldKey) {
        // 자리표시자는 표기가 아니므로 학습시키지 않는다 — `col1` 은 헤더가 비어 있을 때
        // 우리가 붙인 이름이라(DatasetIngestService) 다른 표의 `col1` 과 아무 관계가 없다.
        // 이걸 학습하면 **무관한 표들이 같은 필드로 묶인다.** T115 SSI 가 사전 수집에서 거른
        // 것과 같은 이유이고, 교정 경로에만 그 필터가 없어 실측 중 실제로 오염이 들어갔다.
        if (colName != null && colName.trim().matches("col\\d+")) {
            throw new IllegalArgumentException(
                    "'" + colName + "' 은 헤더가 비어 있어 시스템이 붙인 자리표시자입니다. "
                    + "다른 표의 같은 이름과 무관하므로 학습 대상이 아닙니다 — 원본 엑셀의 헤더를 채워 주세요.");
        }
        String now = LocalDateTime.now().format(TS);
        label(datasetId, colName, stdId, fieldKey, now);
        jdbc.update("DELETE FROM dataset_binding WHERE dataset_id = ? AND col_name = ?", datasetId, colName);
        jdbc.update("""
                INSERT INTO dataset_binding (dataset_id, col_name, std_id, field_key,
                                             confidence, source, evidence, bound_at)
                VALUES (?,?,?,?,1.0,'human','사람이 직접 지정',?)
                """, datasetId, colName, stdId, fieldKey, now);
        learn(colName, stdId, fieldKey, true);
        return Map.of("dataset_id", datasetId, "col_name", colName,
                "std_id", stdId, "field_key", fieldKey,
                "learned", "다음부터 같은 표기는 이 필드로 바인딩된다");
    }

    /**
     * U5 측정의 원료 — 사람이 판정하는 <b>그 순간</b>, 덮이기 직전의 자동 판정을 함께 남긴다.
     *
     * <p>왜 지금인가: 교정이 끝나면 자동 판정은 지워지고(위 DELETE), 사람 판정은 학습에 들어가
     * 다음부터 엔진이 정답을 "외워서" 맞힌다. 사후에 엔진을 다시 돌려 채점하면 시험지를 보고 푼
     * 점수가 된다. 라벨이 생기기 <b>전</b>에 나온 예측만이 정직한 정확도의 재료다(뼈대 §7.1 취지).
     *
     * <p>자동 판정과 같은 값으로 "교정"하면 그것이 곧 <b>확인(agree)</b>이다 — 교정만 기록하면
     * 틀린 것만 모여 정확도가 0 으로 치우친다. 이전 판정이 사람 것이었거나 없었으면 자동 판정의
     * 채점 대상이 아니므로 {@code auto_*} 가 비고 {@code agree} 는 NULL 이다.
     */
    private void label(String datasetId, String colName, String stdId, String fieldKey, String now) {
        List<Map<String, Object>> prev = jdbc.queryForList(
                "SELECT std_id, field_key, source, confidence FROM dataset_binding WHERE dataset_id = ? AND col_name = ?",
                datasetId, colName);
        Map<String, Object> p = prev.isEmpty() ? null : com.aegis.pm.common.Rows.lower(prev.get(0));
        boolean auto = p != null && !"human".equals(p.get("source"));
        Boolean agree = auto ? stdId.equals(p.get("std_id")) && fieldKey.equals(p.get("field_key")) : null;
        jdbc.update("""
                INSERT INTO binding_label (dataset_id, col_name, labeled_at, auto_std, auto_field, auto_source,
                                           auto_conf, human_std, human_field, agree)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """, datasetId, colName, now,
                auto ? p.get("std_id") : null, auto ? p.get("field_key") : null,
                auto ? p.get("source") : null, auto ? p.get("confidence") : null,
                stdId, fieldKey, agree);
    }

    /**
     * 시스템이 만든 바인딩 — 도메인 확장 필드를 그 데이터셋에 이어 붙일 때 쓴다.
     *
     * <p>{@link #correct} 와 달리 <b>human 으로 학습시키지 않는다.</b> 이건 사람의 판단이
     * 아니라 확장 필드를 세우면서 따라온 결과이고, human 으로 기록하면 사람이 실제로 확인한
     * 것과 구분이 사라진다 — L2 층의 신뢰가 그만큼 묽어진다.
     */
    @Transactional
    public void correctAuto(String datasetId, String colName, String stdId, String fieldKey, String evidence) {
        String now = LocalDateTime.now().format(TS);
        jdbc.update("DELETE FROM dataset_binding WHERE dataset_id = ? AND col_name = ?", datasetId, colName);
        jdbc.update("""
                INSERT INTO dataset_binding (dataset_id, col_name, std_id, field_key,
                                             confidence, source, evidence, bound_at)
                VALUES (?,?,?,?,0.8,'rule',?,?)
                """, datasetId, colName, stdId, fieldKey, evidence, now);
        learn(colName, stdId, fieldKey, false);
    }

    /**
     * 잘못 배운 것을 잊는다 — <b>학습에는 취소 경로가 있어야 한다</b>.
     *
     * <p>사람이 실수로 교정하거나, 표준이 바뀌어 옛 학습이 틀리게 되는 일은 반드시 생긴다.
     * 되돌릴 방법이 없으면 그 표기는 영영 틀린 곳에 붙는다 — 사람 교정이 자동 판정을 덮기
     * 때문에 더욱 그렇다. 되돌리기가 없는 학습은 학습이 아니라 각인이다.
     *
     * @return 지운 학습 기록 수
     */
    @Transactional
    public int unlearn(String colNorm, String stdId, String fieldKey) {
        String norm = Absorb.norm(Ingest.nameOf(colNorm));
        int n = (stdId == null || stdId.isBlank())
                ? jdbc.update("DELETE FROM binding_feedback WHERE col_norm = ?", norm)
                : jdbc.update("DELETE FROM binding_feedback WHERE col_norm = ? AND std_id = ? AND field_key = ?",
                        norm, stdId, fieldKey);
        // 그 표기로 붙어 있던 바인딩도 함께 푼다 — 학습만 지우면 화면에는 그대로 남는다
        jdbc.update("DELETE FROM dataset_binding WHERE LOWER(REPLACE(col_name, ' ', '')) = ?", norm);
        return n;
    }

    /** 학습 현황 — 무엇을 얼마나 배웠는가 */
    public List<Map<String, Object>> learned() {
        return jdbc.queryForList("""
                SELECT col_norm, std_id, field_key, hits, human, last_at
                  FROM binding_feedback ORDER BY human DESC, hits DESC
                """).stream().map(Rows::lower).toList();
    }

    // ── 조회 ────────────────────────────────────────────────────────────────

    public List<Map<String, Object>> bindings(String datasetId) {
        return Rows.lower(jdbc.queryForList(
                "SELECT * FROM dataset_binding WHERE dataset_id = ? ORDER BY col_name", datasetId));
    }

    /** 이 데이터셋에서 표준에 붙지 않고 남은 컬럼 — 도메인 확장 후보의 재료 */
    public List<String> unbound(String datasetId) {
        return jdbc.queryForList("""
                SELECT c.name FROM dataset_column c
                 WHERE c.dataset_id = ?
                   AND c.name NOT IN (SELECT col_name FROM dataset_binding WHERE dataset_id = ?)
                 ORDER BY c.col_no
                """, String.class, datasetId, datasetId);
    }

    /**
     * 임베딩 기반 의미 유사도 — <b>아직 없다</b>(T102 NTM Port).
     * 모델이 조달되면 이 한 메서드만 구현하면 {@link #classify} 의 L1 과 L0 사이에 끼워진다.
     */
    @SuppressWarnings("unused")
    private Double semanticScore(String header, String fieldLabel) {
        return null;   // 미조달 — null 은 "모른다"이지 "닮지 않았다"가 아니다
    }

    // ── 보조 ────────────────────────────────────────────────────────────────

    private static int hits(List<Map<String, Object>> rows, int i) {
        return ((Number) Rows.lower(rows.get(i)).get("hits")).intValue();
    }

    private Map<String, Object> result(String datasetId, String stdId, int cols, int matched,
                                       int bound, String level, String note) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("dataset_id", datasetId);
        m.put("std_id", stdId);
        m.put("columns", cols);
        m.put("matched", matched);
        m.put("bound", bound);
        m.put("bind_ratio", cols == 0 ? 0.0 : Math.round((double) bound / cols * 100) / 100.0);
        m.put("level", level);
        m.put("note", note);
        return m;
    }

    private static String str(Object o) {
        return o == null ? null : String.valueOf(o);
    }
}
