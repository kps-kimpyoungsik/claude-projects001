package com.aegis.pm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import com.aegis.pm.dds.BindingEngine;
import com.aegis.pm.dds.DomainBuilder;
import com.aegis.pm.dds.StandardSeeder;

/**
 * 도메인 데이터셋(DOM) 이 지켜야 하는 것.
 *
 * <p>핵심 불변식 둘 — 이게 깨지면 뼈대가 뼈대이기를 그만둔다:
 * <ol>
 *   <li><b>하위는 더할 수만 있다</b> — 부모 필드를 덮으면 같은 이름이 계층마다 다른 뜻이 된다</li>
 *   <li><b>상속은 복제가 아니다</b> — 복제하면 부모가 바뀌어도 자식이 따라가지 않는다</li>
 * </ol>
 */
@SpringBootTest(properties = {
        "wbs.source=excel",
        "wbs.import-on-start=false",
        "spring.datasource.url=jdbc:h2:mem:domtest;DB_CLOSE_DELAY=-1",
        "spring.sql.init.mode=always"
})
class DomainBuilderTest {

    @Autowired StandardSeeder seeder;
    @Autowired BindingEngine binding;
    @Autowired DomainBuilder domains;
    @Autowired JdbcTemplate jdbc;

    @BeforeEach
    void reset() {
        jdbc.update("DELETE FROM standard_field WHERE is_ext = TRUE");
        jdbc.update("DELETE FROM standard_dataset WHERE level = 'DOM'");
        jdbc.update("DELETE FROM binding_feedback");
        jdbc.update("DELETE FROM dataset_binding");
        seeder.seed();
    }

    @Test
    void 미바인딩_컬럼이_도메인_확장_필드가_된다() {
        dataset("DS-YEO", List.of("화면ID", "개발완료여부", "여신등급", "심사단계", "한도소진율"));
        binding.bind("DS-YEO");                     // 2/5 → DOM 후보

        Map<String, Object> r = domains.create("DS-YEO", "여신");

        assertEquals("DOM-여신-SCREEN", r.get("std_id"));
        assertEquals("STD-SCREEN", r.get("parent_std"));
        assertEquals(3, ((List<?>) r.get("ext_fields")).size(), "표준에 없던 3개가 확장 필드가 된다");

        // 근거 데이터셋이 이 DOM 의 인스턴스로 올라가고, 확장 컬럼까지 설명된다
        Map<String, Object> ds = jdbc.queryForMap(
                "SELECT std_id, ds_level FROM dataset WHERE dataset_id = 'DS-YEO'");
        assertEquals("DOM-여신-SCREEN", ds.values().stream().findFirst().orElse(null) instanceof String
                ? jdbc.queryForObject("SELECT std_id FROM dataset WHERE dataset_id='DS-YEO'", String.class)
                : null);
        assertEquals("DOM", jdbc.queryForObject(
                "SELECT ds_level FROM dataset WHERE dataset_id='DS-YEO'", String.class));
        assertTrue(binding.unbound("DS-YEO").isEmpty(), "확장으로 세운 뒤에는 남는 컬럼이 없다");
    }

    @Test
    void 상속은_복제가_아니다() {
        dataset("DS-COPY", List.of("화면ID", "개발완료여부", "여신등급", "심사단계"));
        binding.bind("DS-COPY");
        domains.create("DS-COPY", "여신2");

        // DOM 테이블에는 확장 필드만 저장된다 — 부모 필드는 복제하지 않는다
        Integer own = jdbc.queryForObject(
                "SELECT COUNT(*) FROM standard_field WHERE std_id = 'DOM-여신2-SCREEN'", Integer.class);
        assertEquals(2, own, "저장되는 것은 확장 2개뿐");

        // 조회하면 부모 상속분이 합쳐져 나온다
        List<Map<String, Object>> merged = domains.fieldsOf("DOM-여신2-SCREEN");
        Integer parentCount = jdbc.queryForObject(
                "SELECT COUNT(*) FROM standard_field WHERE std_id = 'STD-SCREEN'", Integer.class);
        assertEquals(parentCount + 2, merged.size(), "조회 시 부모 + 확장");
        assertTrue(merged.stream().anyMatch(f -> "STD-SCREEN".equals(f.get("inherited_from"))),
                "어느 필드가 상속분인지 표시된다");

        // 부모에 필드를 더하면 자식 조회에 바로 따라 나온다 — 복제였다면 안 따라온다
        jdbc.update("""
                INSERT INTO standard_field (std_id, field_key, label, role, data_type, required, is_ext)
                VALUES ('STD-SCREEN','new_field','새필드','text','text',FALSE,FALSE)
                """);
        assertEquals(parentCount + 3, domains.fieldsOf("DOM-여신2-SCREEN").size(),
                "부모가 자라면 자식도 함께 자란다");
    }

    @Test
    void 부모_필드를_덮어쓰지_못한다() {
        // `담당자` 는 STD-SCREEN 의 owner 와 같은 것이라 규칙으로 부모에 붙는다 →
        // 확장 대상이 아니므로 애초에 unbound 에 없다. 여기서는 키 충돌 자체를 막는지 본다.
        dataset("DS-OV", List.of("화면ID", "개발완료여부", "여신등급"));
        binding.bind("DS-OV");
        domains.create("DS-OV", "여신3");

        List<Map<String, Object>> ext = domains.fieldsOf("DOM-여신3-SCREEN").stream()
                .filter(f -> Boolean.TRUE.equals(f.get("is_ext"))).toList();
        List<String> parentKeys = jdbc.queryForList(
                "SELECT field_key FROM standard_field WHERE std_id = 'STD-SCREEN' AND is_ext = FALSE",
                String.class);
        for (Map<String, Object> f : ext) {
            assertFalse(parentKeys.contains(String.valueOf(f.get("field_key"))),
                    "확장 필드가 부모 키와 겹치면 오버라이드가 된다 — 허용하면 뼈대가 무너진다");
        }
    }

    @Test
    void 표준에_안_붙은_데이터셋은_도메인을_만들_수_없다() {
        dataset("DS-ORPHAN", List.of("완전히새로운갑", "완전히새로운을"));
        binding.bind("DS-ORPHAN");   // USR — 부모 없음

        IllegalArgumentException e = assertThrows(IllegalArgumentException.class,
                () -> domains.create("DS-ORPHAN", "무소속"));
        assertTrue(e.getMessage().contains("부모"), "왜 안 되는지 사람이 읽을 수 있어야 한다");
    }

    @Test
    void 여러_도메인이_같은_확장을_쓰면_표준_승격을_제안한다() {
        dataset("DS-D1", List.of("화면ID", "개발완료여부", "위험등급"));
        binding.bind("DS-D1");
        domains.create("DS-D1", "여신");

        dataset("DS-D2", List.of("화면ID", "개발완료여부", "위험등급"));
        binding.bind("DS-D2");
        domains.create("DS-D2", "수신");

        Map<String, Object> p = domains.promotions().stream()
                .filter(x -> "위험등급".equals(x.get("label"))).findFirst().orElseThrow();
        assertEquals(2, ((Number) p.get("domains")).intValue());
        assertTrue(String.valueOf(p.get("why")).contains("도메인 고유가 아니다"));

        // 제안일 뿐 — 시스템이 올리지 않는다
        assertEquals(0, jdbc.queryForObject(
                "SELECT COUNT(*) FROM standard_field WHERE std_id LIKE 'STD-%' AND label = '위험등급'",
                Integer.class), "표준은 합의다. 빈도가 합의를 대신하지 않는다");
    }

    @Test
    void 확장_필드_연결은_사람_교정으로_기록되지_않는다() {
        dataset("DS-AUTO", List.of("화면ID", "개발완료여부", "고유컬럼갑"));
        binding.bind("DS-AUTO");
        domains.create("DS-AUTO", "자동");

        Map<String, Object> b = binding.bindings("DS-AUTO").stream()
                .filter(x -> "고유컬럼갑".equals(x.get("col_name"))).findFirst().orElseThrow();
        assertEquals("rule", b.get("source"),
                "시스템이 만든 연결을 human 으로 기록하면 사람이 실제로 확인한 것과 구분이 사라진다");
        assertNotNull(b.get("evidence"));
    }

    private void dataset(String id, List<String> headers) {
        jdbc.update("DELETE FROM dataset_column WHERE dataset_id = ?", id);
        jdbc.update("DELETE FROM dataset WHERE dataset_id = ?", id);
        jdbc.update("INSERT INTO dataset (dataset_id, name, row_count, col_count) VALUES (?,?,0,?)",
                id, id, headers.size());
        for (int i = 0; i < headers.size(); i++) {
            jdbc.update("INSERT INTO dataset_column (dataset_id, col_no, name, data_type) VALUES (?,?,?,'text')",
                    id, i, headers.get(i));
        }
    }
}
