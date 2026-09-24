package com.aegis.pm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import com.aegis.pm.dds.BindingEngine;
import com.aegis.pm.dds.StandardSeeder;

/**
 * 표준 뼈대가 지켜야 하는 것, 그리고 <b>학습이 실제로 일어나는가</b>.
 *
 * <p>학습의 정의는 하나다 — <b>관측·교정이 쌓이면 다음 판정이 달라진다.</b>
 * 그게 안 되면 이 시스템은 규칙 엔진이지 학습하는 시스템이 아니다. 여기서 못박는다.
 */
@SpringBootTest(properties = {
        "wbs.source=excel",
        "wbs.import-on-start=false",
        "spring.datasource.url=jdbc:h2:mem:stdbindtest;DB_CLOSE_DELAY=-1",
        "spring.sql.init.mode=always"
})
class StandardBindingTest {

    @Autowired StandardSeeder seeder;
    @Autowired BindingEngine binding;
    @Autowired JdbcTemplate jdbc;

    @BeforeEach
    void seedStandards() {
        jdbc.update("DELETE FROM binding_feedback");
        jdbc.update("DELETE FROM dataset_binding");
        seeder.seed();
    }

    // ── 1. 뼈대 ─────────────────────────────────────────────────────────────

    @Test
    void 표준_5종과_관계_4건이_선다() {
        assertEquals(5, jdbc.queryForObject(
                "SELECT COUNT(*) FROM standard_dataset WHERE level = 'STD'", Integer.class));
        assertEquals(4, jdbc.queryForObject("SELECT COUNT(*) FROM standard_relation", Integer.class));

        // required 필드가 없는 표준은 "이 표준이라 할 수 있는 조건"이 없는 것이다
        for (String std : List.of("STD-TASK", "STD-SCREEN", "STD-DEFECT", "STD-PERSON", "STD-ISSUE")) {
            Integer req = jdbc.queryForObject(
                    "SELECT COUNT(*) FROM standard_field WHERE std_id = ? AND required = TRUE",
                    Integer.class, std);
            assertTrue(req != null && req > 0, std + " 에 required 필드가 있어야 한다");
        }
    }

    @Test
    void 모든_표준_필드가_grain과_의도를_갖는다() {
        // 의도 없는 필드는 6개월 뒤 아무도 못 고친다 (05 ADR V1 과 같은 이유)
        Integer noIntent = jdbc.queryForObject(
                "SELECT COUNT(*) FROM standard_field WHERE intent IS NULL OR intent = ''", Integer.class);
        assertEquals(0, noIntent);
        Integer noGrain = jdbc.queryForObject(
                "SELECT COUNT(*) FROM standard_dataset WHERE grain IS NULL OR grain = ''", Integer.class);
        assertEquals(0, noGrain, "grain 이 없으면 두 표가 같은 표준에 붙어도 집계 단위가 어긋난다");
    }

    // ── 2. 바인딩 ───────────────────────────────────────────────────────────

    @Test
    void 결함_표는_STD_DEFECT에_붙고_매핑률이_나온다() {
        dataset("DS-DEF", List.of("결함번호", "등록일", "결함상태", "결함내용", "심각도", "사내메모"));
        Map<String, Object> r = binding.bind("DS-DEF");

        assertEquals("STD-DEFECT", r.get("std_id"));
        assertEquals("STD", r.get("level"), "5/6 = 0.83 → 표준 인스턴스");
        assertTrue((Double) r.get("bind_ratio") >= BindingEngineProbe.BIND_STD);
        assertEquals(List.of("사내메모"), binding.unbound("DS-DEF"), "표준에 없는 컬럼은 버리지 않고 남는다");
    }

    @Test
    void 절반만_맞으면_도메인_확장_후보가_된다() {
        dataset("DS-HALF", List.of("화면ID", "개발완료여부", "여신등급", "심사단계", "한도소진율"));
        Map<String, Object> r = binding.bind("DS-HALF");

        assertEquals("DOM", r.get("level"), "2/5 = 0.4 → 도메인 확장 후보");
        assertEquals("STD-SCREEN", r.get("std_id"));
        assertEquals(3, binding.unbound("DS-HALF").size(), "표준에 없는 3개가 도메인 확장의 재료다");
    }

    @Test
    void 아무것도_안_맞으면_거부가_아니라_USR로_남는다() {
        dataset("DS-NEW", List.of("완전히새로운것갑", "완전히새로운것을", "완전히새로운것병"));
        Map<String, Object> r = binding.bind("DS-NEW");

        assertEquals("USR", r.get("level"));
        assertNull(r.get("std_id"));
        // 거부는 자격 게이트(Phase 4)의 일이고 여기는 "표준에 맞는가"만 본다
        assertEquals(3, jdbc.queryForObject(
                "SELECT COUNT(*) FROM dataset_column WHERE dataset_id = 'DS-NEW'", Integer.class),
                "바인딩 실패가 데이터를 지우지 않는다");
    }

    // ── 3. 학습 — 이 시스템이 학습한다고 말할 수 있는 근거 ──────────────────

    @Test
    void 사람이_한_번_고치면_다음_데이터셋에_적용된다() {
        // `처리담당` 은 사전에도 표준에도 없는 표기 — 처음엔 못 붙는다
        assertNull(binding.classify("처리담당"));

        dataset("DS-A", List.of("결함번호", "처리담당"));
        binding.bind("DS-A");
        binding.correct("DS-A", "처리담당", "STD-DEFECT", "owner");   // 사람이 알려 준다

        // 다른 데이터셋의 같은 표기가 이제 자동으로 붙는다 — 이것이 학습이다
        BindingEngine.Hit hit = binding.classify("처리담당");
        assertNotNull(hit, "사람이 알려 준 표기는 다음부터 인식돼야 한다");
        assertEquals("STD-DEFECT", hit.stdId());
        assertEquals("owner", hit.fieldKey());
        assertEquals("human", hit.source());
        assertEquals(1.0, hit.confidence());

        dataset("DS-B", List.of("결함번호", "처리담당"));
        Map<String, Object> r = binding.bind("DS-B");
        assertEquals(2, r.get("bound"), "새 데이터셋에서도 두 컬럼 다 붙는다");
    }

    @Test
    void 사람_교정은_자동_판정이_덮지_못한다() {
        dataset("DS-C", List.of("담당자"));
        binding.bind("DS-C");                                      // 규칙으로 어딘가 붙음
        binding.correct("DS-C", "담당자", "STD-TASK", "owner");     // 사람이 STD-TASK 로 지정

        for (int i = 0; i < 5; i++) {                              // 자동 관측을 5회 더 쌓아도
            binding.learn("담당자", "STD-SCREEN", "owner", false);
        }
        BindingEngine.Hit hit = binding.classify("담당자");
        assertEquals("STD-TASK", hit.stdId(), "사람이 정한 것은 관측 누적으로 뒤집히지 않는다");
        assertEquals("human", hit.source());
    }

    @Test
    void 관측이_쌓이면_확신도가_오른다() {
        binding.learn("모호한표기", "STD-ISSUE", "content", false);
        double first = binding.classify("모호한표기").confidence();

        for (int i = 0; i < 4; i++) binding.learn("모호한표기", "STD-ISSUE", "content", false);
        double later = binding.classify("모호한표기").confidence();

        assertTrue(later > first, "관측이 쌓이면 확신이 올라야 한다 (" + first + " → " + later + ")");
        assertTrue(later < 1.0, "통계는 사람이 아니다 — 1.0 에 닿지 않는다");
    }

    @Test
    void 자리표시자는_학습시키지_않는다() {
        // `col1` 은 헤더가 비어 있을 때 우리가 붙인 이름이라 다른 표의 `col1` 과 무관하다.
        // 학습하면 무관한 표들이 같은 필드로 묶인다 — 실측 중 실제로 오염이 들어갔던 경로다.
        dataset("DS-PLACEHOLDER", List.of("col1", "col2"));
        org.junit.jupiter.api.Assertions.assertThrows(IllegalArgumentException.class,
                () -> binding.correct("DS-PLACEHOLDER", "col1", "STD-TASK", "task_name"));

        Integer leaked = jdbc.queryForObject(
                "SELECT COUNT(*) FROM binding_feedback WHERE col_norm LIKE 'col%'", Integer.class);
        assertEquals(0, leaked, "거부된 교정은 학습 기록에도 남지 않는다");
    }

    @Test
    void 사람_교정은_재바인딩에도_살아남는다() {
        // bind() 는 득표 1위 표준의 바인딩만 저장한다. 사람이 다른 표준으로 고쳐 두면
        // 그 교정이 재바인딩에서 버려져 L2 우선 원칙이 이 경로에서만 깨졌다(실측 발견).
        dataset("DS-KEEP", List.of("결함번호", "등록일", "결함상태", "특이사항"));
        binding.bind("DS-KEEP");                                       // 득표 1위 = STD-DEFECT
        binding.correct("DS-KEEP", "특이사항", "STD-ISSUE", "content"); // 다른 표준으로 교정

        binding.bind("DS-KEEP");                                       // 재바인딩

        Map<String, Object> kept = binding.bindings("DS-KEEP").stream()
                .filter(b -> "특이사항".equals(b.get("col_name"))).findFirst().orElse(null);
        assertNotNull(kept, "사람이 고친 바인딩이 재바인딩에서 사라지면 안 된다");
        assertEquals("STD-ISSUE", kept.get("std_id"));
        assertEquals("human", kept.get("source"));
    }

    @Test
    void 공통_표기는_그_표의_표준_쪽으로_붙는다() {
        // `담당자` 는 STD-TASK 에도 STD-DEFECT 에도 정당하게 있다. 맥락 없이 통계로 하나에
        // 고정하면 결함 표의 `담당자` 가 STD-TASK 로 판정돼 그 표의 바인딩에서 버려진다.
        for (int i = 0; i < 5; i++) binding.learn("담당자", "STD-TASK", "owner", false);
        assertEquals("STD-TASK", binding.classify("담당자").stdId(), "맥락 없으면 통계를 따른다");

        dataset("DS-CTX", List.of("결함번호", "등록일", "결함상태", "결함내용", "담당자"));
        Map<String, Object> r = binding.bind("DS-CTX");

        assertEquals("STD-DEFECT", r.get("std_id"));
        Map<String, Object> owner = binding.bindings("DS-CTX").stream()
                .filter(b -> "담당자".equals(b.get("col_name"))).findFirst().orElse(null);
        assertNotNull(owner, "이 표의 표준에도 있는 표기가 버려지면 안 된다");
        assertEquals("STD-DEFECT", owner.get("std_id"), "결함 표의 담당자는 결함의 담당자다");
    }

    @Test
    void 맥락보다_사람_교정이_먼저다() {
        dataset("DS-PRI", List.of("결함번호", "결함상태", "특이컬럼"));
        binding.bind("DS-PRI");
        binding.correct("DS-PRI", "특이컬럼", "STD-ISSUE", "content");

        // 맥락(STD-DEFECT)이 주어져도 사람이 지정한 STD-ISSUE 가 이긴다
        BindingEngine.Hit hit = binding.classify("특이컬럼", "STD-DEFECT");
        assertEquals("STD-ISSUE", hit.stdId());
        assertEquals("human", hit.source());
    }

    @Test
    void 잘못_배운_것을_잊을_수_있다() {
        binding.learn("오학습표기", "STD-TASK", "owner", true);
        assertNotNull(binding.classify("오학습표기"));

        int removed = binding.unlearn("오학습표기", null, null);
        assertEquals(1, removed);
        assertNull(binding.classify("오학습표기"),
                "되돌리기 없는 학습은 학습이 아니라 각인이다");
    }

    @Test
    void 학습_현황이_무엇을_배웠는지_보여준다() {
        binding.learn("테스트표기", "STD-TASK", "owner", true);
        Map<String, Object> row = binding.learned().stream()
                .filter(r -> "테스트표기".equals(r.get("col_norm"))).findFirst().orElseThrow();
        assertEquals(1, ((Number) row.get("human")).intValue());
        assertTrue(((Number) row.get("hits")).intValue() >= BindingEngineProbe.HUMAN_WEIGHT,
                "사람 교정은 자동 관측보다 무겁게 쌓인다");
    }

    // ── 보조 ────────────────────────────────────────────────────────────────

    private void dataset(String id, List<String> headers) {
        jdbc.update("DELETE FROM dataset_column WHERE dataset_id = ?", id);
        jdbc.update("DELETE FROM dataset WHERE dataset_id = ?", id);
        jdbc.update("INSERT INTO dataset (dataset_id, name, row_count, col_count) VALUES (?,?,0,?)",
                id, id, headers.size());
        for (int i = 0; i < headers.size(); i++) {
            jdbc.update("INSERT INTO dataset_column (dataset_id, col_no, name) VALUES (?,?,?)",
                    id, i, headers.get(i));
        }
    }

    /** package-private 상수의 테스트용 사본 */
    private static final class BindingEngineProbe {
        static final double BIND_STD = 0.7;
        static final int HUMAN_WEIGHT = 10;
    }
}
