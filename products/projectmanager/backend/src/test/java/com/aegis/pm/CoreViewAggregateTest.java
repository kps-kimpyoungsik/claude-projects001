package com.aegis.pm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.HashMap;
import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import com.aegis.pm.dataset.DatasetWriter;
import com.aegis.pm.dds.CoreView;

/**
 * 뷰 데이터셋의 <b>집계 경로</b>가 원본과 같은 값을 내는가.
 *
 * <p>행 조회({@code rows})만 분기하고 집계({@code forEachRow})를 빠뜨리면 <b>집계가 조용히
 * 0건이 된다</b> — 오류가 아니라 빈 결과라서 화면에는 "데이터 없음"으로만 보이고, 원인을
 * 찾기 전까지 아무도 틀린 줄 모른다. 실측 중 실제로 그 상태였다.
 */
@SpringBootTest(properties = {
        "wbs.source=excel",
        "wbs.import-on-start=false",
        "spring.datasource.url=jdbc:h2:mem:coreviewtest;DB_CLOSE_DELAY=-1",
        "spring.sql.init.mode=always"
})
class CoreViewAggregateTest {

    @Autowired CoreView views;
    @Autowired DatasetWriter writer;
    @Autowired JdbcTemplate jdbc;

    @BeforeEach
    void seedDefects() {
        jdbc.update("DELETE FROM defect");
        insert("DF-2026-001", "2026-07-01", "조치완료", "보통");
        insert("DF-2026-002", "2026-07-02", "조치완료", "낮음");
        insert("DF-2026-003", "2026-08-01", "대기", "높음");
        insert("DF-2026-004", "2026-08-02", "", "보통");      // 빈 상태 — 집계에서 사라지면 안 된다
        views.register();
    }

    @Test
    void 뷰는_행을_복사하지_않는다() {
        Integer copied = jdbc.queryForObject(
                "SELECT COUNT(*) FROM dataset_row WHERE dataset_id = ?", Integer.class, "DS-VIEW-defect");
        assertEquals(0, copied, "행을 복사하면 같은 사실이 두 벌이 되고 원본 변경이 안 따라온다");

        Integer cols = jdbc.queryForObject(
                "SELECT COUNT(*) FROM dataset_column WHERE dataset_id = ?", Integer.class, "DS-VIEW-defect");
        assertTrue(cols != null && cols > 0, "메타(컬럼)는 등록돼 있어야 바인딩이 가능하다");
    }

    @Test
    void 집계_경로가_원본과_같은_값을_낸다() {
        // forEachRow — 위젯 집계가 쓰는 경로
        Map<String, Integer> byStatus = new HashMap<>();
        writer.forEachRow("DS-VIEW-defect",
                r -> byStatus.merge(nz(r.get("결함상태")), 1, Integer::sum));

        assertEquals(4, byStatus.values().stream().mapToInt(Integer::intValue).sum(),
                "집계가 조용히 0건이 되면 화면에는 '데이터 없음'으로만 보인다");
        assertEquals(2, byStatus.get("조치완료"));
        assertEquals(1, byStatus.get("대기"));
        assertEquals(1, byStatus.get("(빈값)"), "빈 값도 하나의 값이다 — 세지 않으면 합계가 어긋난다");
    }

    @Test
    void 행_조회와_집계가_같은_것을_본다() {
        int viaRows = writer.rows("DS-VIEW-defect").size();
        int[] viaEach = {0};
        writer.forEachRow("DS-VIEW-defect", r -> viaEach[0]++);
        assertEquals(viaRows, viaEach[0], "두 경로가 다른 수를 보면 화면과 위젯이 어긋난다");
    }

    @Test
    void 원본이_바뀌면_뷰도_바뀐다() {
        int before = writer.rows("DS-VIEW-defect").size();
        insert("DF-2026-005", "2026-08-03", "신규", "보통");

        // 재등록 없이도 행은 원본에서 읽으므로 즉시 반영된다 — 복제였다면 그대로였다
        assertEquals(before + 1, writer.rows("DS-VIEW-defect").size());
    }

    @Test
    void 뷰가_아닌_데이터셋은_기존_경로를_쓴다() {
        assertFalse(CoreView.isView("DS-20260911-182050-1"));
        assertTrue(CoreView.isView("DS-VIEW-defect"));
    }

    private void insert(String id, String regDt, String status, String severity) {
        jdbc.update("""
                INSERT INTO defect (defect_id, reg_dt, status, severity, content, source)
                VALUES (?,?,?,?,'테스트','manual')
                """, id, regDt, status, severity);
    }

    private static String nz(String v) {
        return v == null || v.isBlank() ? "(빈값)" : v;
    }
}
