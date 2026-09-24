package com.aegis.pm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import com.aegis.pm.dds.Absorb;
import com.aegis.pm.dds.VocabSeeder;
import com.aegis.pm.dds.VocabStore;

/**
 * 어휘 사전이 지켜야 하는 것 셋:
 *
 * <ol>
 *   <li><b>경계</b> — 개인정보·문장·값이 사전에 들어가지 않는다 (이 Phase 의 SAFETY 지점)</li>
 *   <li><b>매칭</b> — 동의어로 등록한 표기가 실제로 대표어를 찾아온다</li>
 *   <li><b>진화</b> — 모르는 토큰이 3회 나오면 draft 후보가 생기고, 사람 판정은 덮이지 않는다</li>
 * </ol>
 */
@SpringBootTest(properties = {
        "wbs.source=excel",
        "wbs.import-on-start=false",
        "spring.datasource.url=jdbc:h2:mem:vocabtest;DB_CLOSE_DELAY=-1",
        "spring.sql.init.mode=always"
})
class VocabTest {

    @Autowired VocabStore store;
    @Autowired VocabSeeder seeder;
    @Autowired JdbcTemplate jdbc;

    // ── 1. 경계 ─────────────────────────────────────────────────────────────

    @Test
    void 개인정보와_값은_흡수하지_않는다() {
        assertTrue(Absorb.isPersonColumn("담당자"), "담당자 컬럼은 값 흡수 금지 대상");
        assertTrue(Absorb.isPersonColumn("PM(책임)"), "괄호·약어가 섞여도 잡아야 한다");
        assertFalse(Absorb.isPersonColumn("개발완료여부"));

        assertNotNull(Absorb.rejectReason("010-1234-5678"), "전화번호");
        assertNotNull(Absorb.rejectReason("hong@example.com"), "이메일");
        assertNotNull(Absorb.rejectReason("901010-1234567"), "주민번호 형식");
        assertNotNull(Absorb.rejectReason("2026-09-14"), "날짜 값");
        assertNotNull(Absorb.rejectReason("1,234"), "숫자 값");
        assertNotNull(Absorb.rejectReason("85%"), "단위 붙은 숫자 값");
        assertNotNull(Absorb.rejectReason("통합테스트 개발 완료 범위 현행화.xlsx"), "파일명");
        assertNotNull(Absorb.rejectReason("이 화면은 여신 한도를 조회하는 화면입니다"), "문장");

        assertNull(Absorb.rejectReason("개발완료여부"));
        assertNull(Absorb.rejectReason("기획 피드백"));
    }

    @Test
    void 경계_밖_토큰은_자동_등재되지_않는다() {
        Map<String, Object> bad = new LinkedHashMap<>();
        bad.put("term", "010-1234-5678");
        assertThrows(IllegalArgumentException.class, () -> store.save(bad, "rule", "자동 흡수 시도"));
    }

    // ── 2. 매칭 ─────────────────────────────────────────────────────────────

    @Test
    void PM을_넣으면_담당자가_나온다() {
        Map<String, Object> t = new LinkedHashMap<>();
        t.put("level", "STD");
        t.put("kind", "attribute");
        t.put("term", "담당자");
        t.put("definition", "작업을 책임지는 사람");
        t.put("intent", "작업별 책임 소재를 가리는 필드");
        t.put("synonyms", "PM, 책임자, 담 당 자");
        t.put("status", "approved");
        store.save(t, "human", "매칭 테스트 시드");

        assertEquals("담당자", store.match("담당자").get("term"));
        assertEquals("synonym", store.match("PM").get("matched_by"));
        assertEquals("담당자", store.match("담 당 자").get("term"), "공백 차이는 정규화 단계에서 잡힌다");
        assertNull(store.match("존재하지않는컬럼명"), "못 찾으면 null — 아무거나 돌려주지 않는다");

        Integer used = jdbc.queryForObject(
                "SELECT usage_count FROM vocab_term WHERE term = ?", Integer.class, "담당자");
        assertEquals(3, used, "매칭 성공 3회가 사용 횟수로 남는다");
    }

    @Test
    void 동의어_부분문자열로_오매칭되지_않는다() {
        Map<String, Object> t = new LinkedHashMap<>();
        t.put("term", "심각도");
        t.put("synonyms", "severity");
        t.put("status", "approved");
        store.save(t, "human", "오매칭 테스트 시드");
        // "eve" 는 "severity" 의 부분문자열이지만 쉼표 단위 재판정에서 걸러져야 한다
        assertNull(store.match("eve"));
    }

    // ── 3. 진화 ─────────────────────────────────────────────────────────────

    @Test
    void 모르는_토큰이_3회_나오면_draft가_생긴다() {
        String token = "한도소진율";
        for (int i = 0; i < VocabStoreProbe.MISS_TO_DRAFT; i++) assertNull(store.match(token));

        List<Map<String, Object>> drafts = store.terms("LOCAL", null, token);
        assertEquals(1, drafts.size(), "3회째에 후보가 정확히 1건 생긴다");
        assertEquals("draft", drafts.get(0).get("status"), "등재가 아니라 후보다");

        store.match(token);   // 4회째 — 이미 후보가 있으므로 중복 생성되지 않는다
        assertEquals(1, store.terms("LOCAL", null, token).size());
    }

    @Test
    void 사람이_정한_것은_자동_판정이_덮지_않는다() {
        Map<String, Object> mine = new LinkedHashMap<>();
        mine.put("term", "진척률");
        mine.put("definition", "사람이 확정한 정의");
        mine.put("status", "approved");
        String id = store.save(mine, "human", "사람 등록");

        Map<String, Object> auto = new LinkedHashMap<>();
        auto.put("term", "진척률");
        auto.put("definition", "(자동 초안) 덮어쓰면 안 되는 값");
        store.save(auto, "rule", "자동 흡수");

        assertEquals("사람이 확정한 정의", store.term(id).get("definition"));
    }

    @Test
    void 정의를_고치면_버전과_이력이_남는다() {
        Map<String, Object> t = new LinkedHashMap<>();
        t.put("term", "결함유형");
        t.put("definition", "첫 정의");
        String id = store.save(t, "human", "최초 등록");

        t.put("definition", "고친 정의");
        store.save(t, "human", "용어 정의 보완");

        assertEquals(2, ((Number) store.term(id).get("version")).intValue());
        List<Map<String, Object>> history = store.history(id);
        assertEquals(2, history.size(), "생성 1건 + 변경 1건");
        assertEquals("첫 정의", history.get(0).get("before_val"), "이전 값이 덮이지 않고 남는다");
    }

    // ── 4. 시드 ─────────────────────────────────────────────────────────────

    @Test
    void 시드는_분야와_형식을_실측_없이도_세운다() {
        int n = seeder.seedFixed();
        assertEquals(11, n, "분야 7종 + 식별자 형식 4종");
        assertEquals(7, store.terms("STD", "concept", null).size());

        Map<String, Object> src = store.sources().stream()
                .filter(s -> VocabSeeder.SRC_FIXED.equals(s.get("source_id"))).findFirst().orElseThrow();
        assertNotNull(src.get("scope_out"), "무엇을 일부러 뺐는지도 남는다");

        seeder.seedFixed();   // 재실행해도 늘지 않는다
        assertEquals(7, store.terms("STD", "concept", null).size());
    }

    // ── 5. 공통 사전 vs 특정 도메인 사전 ────────────────────────────────────

    @Test
    void 여러_표에_걸친_헤더는_공통_한_표뿐이면_로컬이_된다() {
        // 다른 테스트가 쓰는 표기와 겹치지 않게 고유한 이름을 쓴다 (우연 통과 방지)
        seedHeadersFrom(Map.of(
                "DS-A", List.of("공통헤더갑", "공통헤더을", "A전용컬럼"),
                "DS-B", List.of("공통헤더갑", "공통헤더을", "B전용컬럼")));
        seeder.seedHeaders();

        assertEquals("STD", levelOf("공통헤더갑"), "두 표에 모두 있으면 전사 공통 후보");
        assertEquals("STD", levelOf("공통헤더을"));
        assertEquals("LOCAL", levelOf("A전용컬럼"), "한 표에만 있으면 그 표 범위");
        assertEquals("LOCAL", levelOf("B전용컬럼"));
    }

    @Test
    void 재시드가_계층을_올리지_않고_제안만_한다() {
        seedHeadersFrom(Map.of("DS-C", List.of("승격후보")));
        seeder.seedHeaders();
        assertEquals("LOCAL", levelOf("승격후보"));

        // 같은 헤더가 다른 표에도 생겼다 — 이제 공통 근거가 있다
        seedHeadersFrom(Map.of("DS-C", List.of("승격후보"), "DS-D", List.of("승격후보")));
        seeder.seedHeaders();
        assertEquals("LOCAL", levelOf("승격후보"), "시스템이 올리지 않는다 (05 ADR V5)");

        Map<String, Object> p = store.promotions().stream()
                .filter(r -> "승격후보".equals(r.get("term"))).findFirst().orElseThrow();
        assertEquals("STD", p.get("suggest_level"));
        assertTrue(String.valueOf(p.get("why")).contains("표 2개"), "왜 올려야 하는지가 근거로 나온다");

        // 사람이 올리면 그때 바뀌고 이력에 promote 로 남는다
        store.save(Map.of("term", "승격후보", "level", "STD"), "human", "공통 승격 승인");
        assertEquals("STD", levelOf("승격후보"));
    }

    @Test
    void 도메인_어휘는_소속_도메인을_갖는다() {
        jdbc.update("DELETE FROM ia_screen");
        jdbc.update("INSERT INTO ia_screen (seq, d1, d2) VALUES (1, '여신', '한도조회')");
        seeder.seedAreas();

        Map<String, Object> t = store.terms("DOM", null, "여신").get(0);
        assertEquals(VocabSeeder.AREA_DOMAIN, t.get("domain"), "어느 도메인 사전에 속하는지가 비면 특정 사전이 성립하지 않는다");
    }

    private String levelOf(String term) {
        return jdbc.queryForObject("SELECT level FROM vocab_term WHERE term = ?", String.class, term);
    }

    /** dataset_column 에 헤더만 심는다 — 시드가 읽는 것은 컬럼명뿐이다 */
    private void seedHeadersFrom(Map<String, List<String>> byDataset) {
        jdbc.update("DELETE FROM dataset_column");
        byDataset.forEach((ds, cols) -> {
            for (int i = 0; i < cols.size(); i++) {
                jdbc.update("INSERT INTO dataset_column (dataset_id, col_no, name) VALUES (?,?,?)",
                        ds, i, cols.get(i));
            }
        });
    }

    /** {@link VocabStore#MISS_TO_DRAFT} 가 package-private 이라 테스트에서만 읽는 상수 사본 */
    private static final class VocabStoreProbe {
        static final int MISS_TO_DRAFT = 3;
    }
}
