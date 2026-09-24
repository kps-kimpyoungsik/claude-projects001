package com.aegis.pm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
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
import com.aegis.pm.dds.MetricService;
import com.aegis.pm.dds.StandardSeeder;

/**
 * U5-min 통과 기준(뼈대 §14 축소판): precision 이 <b>사람 판정 직전의 예측</b>으로 계산되고,
 * 확인(같은 값)은 맞음·교정(다른 값)은 틀림으로 세며, 스냅샷이 추이로 쌓인다.
 */
@SpringBootTest(properties = {
        "wbs.source=excel",
        "wbs.import-on-start=false",
        "spring.datasource.url=jdbc:h2:mem:metrictest;DB_CLOSE_DELAY=-1",
        "spring.sql.init.mode=always"
})
class MetricLoopTest {

    @Autowired StandardSeeder seeder;
    @Autowired BindingEngine binding;
    @Autowired MetricService metrics;
    @Autowired JdbcTemplate jdbc;

    @BeforeEach
    void reset() {
        for (String t : List.of("binding_label", "struct_metric", "binding_feedback", "dataset_binding",
                "dataset_column", "dataset")) {
            jdbc.update("DELETE FROM " + t);
        }
        seeder.seed();
        List<String> headers = List.of("결함번호", "등록일", "결함상태", "결함내용", "심각도", "사내메모");
        jdbc.update("INSERT INTO dataset (dataset_id, name, row_count, col_count) VALUES ('DS-M','DS-M',0,?)",
                headers.size());
        for (int i = 0; i < headers.size(); i++) {
            jdbc.update("INSERT INTO dataset_column (dataset_id, col_no, name) VALUES ('DS-M',?,?)", i, headers.get(i));
        }
        binding.bind("DS-M");
    }

    private Map<String, Object> auto(String col) {
        return jdbc.queryForMap("SELECT std_id, field_key FROM dataset_binding WHERE dataset_id='DS-M' AND col_name=?", col);
    }

    @Test
    void 라벨이_없으면_precision_은_비어_있고_믿을_수_없다고_표시한다() {
        Map<String, Object> all = metrics.current().get(0);
        assertEquals("ALL", all.get("scope"));
        assertNull(all.get("precision"), "라벨 0건에서 숫자를 지어내지 않는다");
        assertEquals(false, all.get("reliable"));
        assertEquals(1.0, all.get("auto_rate"), "아직 사람이 손대지 않았다");
    }

    @Test
    void 확인만_하면_auto_rate_는_떨어지지_않고_사람이_값을_바꾸면_떨어진다() {
        Map<String, Object> a = auto("결함번호");
        binding.correct("DS-M", "결함번호", (String) a.get("STD_ID"), (String) a.get("FIELD_KEY"));   // 확인
        assertEquals(1.0, metrics.current().get(0).get("auto_rate"), "검증했다고 자동화가 후퇴한 것처럼 보이면 안 된다");

        binding.correct("DS-M", "결함번호", "STD-DEFECT", "status");   // 확인 뒤 사람이 다른 값으로 바꿈
        assertTrue((Double) metrics.current().get(0).get("auto_rate") < 1.0, "최종 값이 자동 판정과 다르면 자동 아님");
    }

    @Test
    void 확인은_맞음_교정은_틀림으로_센다() {
        Map<String, Object> a = auto("결함번호");
        binding.correct("DS-M", "결함번호", (String) a.get("STD_ID"), (String) a.get("FIELD_KEY"));   // 확인
        binding.correct("DS-M", "심각도", "STD-DEFECT", "status");                                      // 교정(오답 주입)
        binding.correct("DS-M", "심각도", "STD-DEFECT", "severity");                                    // 사람→사람: 채점 제외

        Map<String, Object> all = metrics.current().get(0);
        assertEquals(2, all.get("labels"), "사람 판정을 다시 고친 것은 자동 판정 채점이 아니다");
        assertEquals(0.5, (Double) all.get("precision"), 1e-9);
        assertTrue((Double) all.get("auto_rate") < 1.0);
        assertEquals(3, jdbc.queryForObject("SELECT COUNT(*) FROM binding_label", Integer.class),
                "채점 제외분도 라벨 이력으로는 남는다");
    }

    @Test
    void 스냅샷이_추이로_쌓이고_표본이_적으면_회귀로_오보하지_않는다() {
        Map<String, Object> a = auto("결함번호");
        binding.correct("DS-M", "결함번호", (String) a.get("STD_ID"), (String) a.get("FIELD_KEY"));
        metrics.snapshot();
        binding.correct("DS-M", "등록일", "STD-DEFECT", "status");   // precision 1.0 → 0.5
        Map<String, Object> s = metrics.snapshot();

        assertFalse(((List<?>) s.get("regressions")).stream().findAny().isPresent(),
                "라벨 2건의 흔들림은 회귀가 아니다 (MIN_LABELS)");
        List<Map<String, Object>> h = metrics.history("ALL");
        assertEquals(2, h.size());
        assertEquals(1.0, ((Number) h.get(0).get("precision")).doubleValue(), 1e-9);
        assertEquals(0.5, ((Number) h.get(1).get("precision")).doubleValue(), 1e-9);
    }

    @Test
    void 표본이_충분하면_정확도_하락을_회귀로_잡는다() {
        label(60, true);
        metrics.snapshot();                       // precision 1.00 (60/60)
        label(10, false);                         // 사전·표준 변경 뒤 오답이 섞였다고 가정
        Map<String, Object> s = metrics.snapshot();   // 60/70 = 0.857 → -14%p

        List<?> reg = (List<?>) s.get("regressions");
        assertEquals(List.of("ALL", "STD-DEFECT"), reg.stream().map(r -> ((Map<?, ?>) r).get("scope")).toList(),
                "전체와 원인 표준을 함께 지목한다");
    }

    @Test
    void 엉뚱한_표준으로_잘못_묶은_회귀는_잘못_묶은_표준을_지목한다() {
        label(60, true);
        metrics.snapshot();
        // 엔진이 다른 표준의 컬럼을 STD-DEFECT 로 잘못 묶기 시작했다 — 사람은 STD-OTHER 로 고친다.
        // human_std 로 거르면 이 오답이 STD-DEFECT 에 안 잡혀 원인 표준을 놓친다.
        label(10, false, "STD-OTHER");
        Map<String, Object> s = metrics.snapshot();

        List<?> reg = (List<?>) s.get("regressions");
        assertEquals(List.of("ALL", "STD-DEFECT"), reg.stream().map(r -> ((Map<?, ?>) r).get("scope")).toList());
    }

    private void label(int n, boolean agree) {
        label(n, agree, "STD-DEFECT");
    }

    private void label(int n, boolean agree, String humanStd) {
        int base = jdbc.queryForObject("SELECT COUNT(*) FROM binding_label", Integer.class);
        for (int i = 0; i < n; i++) {
            jdbc.update("""
                    INSERT INTO binding_label (dataset_id, col_name, labeled_at, auto_std, auto_field,
                                               human_std, human_field, agree)
                    VALUES ('DS-M', ?, '2026-09-23 00:00:00', 'STD-DEFECT', 'x', ?, 'x', ?)""",
                    "c" + (base + i), humanStd, agree);
        }
    }
}
