package com.aegis.pm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;

import com.aegis.pm.config.WbsProperties;
import com.aegis.pm.domain.ProgressTree;
import com.aegis.pm.domain.Task;
import com.aegis.pm.domain.WbsModel;
import com.aegis.pm.excel.ExcelSource;
import com.aegis.pm.excel.SheetTableReader;
import com.aegis.pm.excel.WbsExcelReader;
import com.aegis.pm.repo.ExcelWbsRepository;
import com.aegis.pm.service.WbsService;

/**
 * 엑셀 판독·진척 재계산 정합 — 모델 파싱이 깨지면 모든 화면이 동시에 깨지므로 여기서 고정한다.
 */
class WbsReadTest {

    static WbsProperties props() {
        WbsProperties p = new WbsProperties();
        p.setFile("../중소기업중앙회_WEB통합자금관리시스템고도화_wbs_v1.0_20260831.xlsx");
        return p;
    }

    static WbsService service() {
        WbsProperties props = props();
        ExcelSource source = new ExcelSource(props);
        return new WbsService(new ExcelWbsRepository(
                new WbsExcelReader(source, props), new SheetTableReader(source)));
    }

    @Test
    void 모델_파싱_정합() {
        WbsModel m = service().modelAll();

        assertFalse(m.tasks().isEmpty(), "작업이 하나도 파싱되지 않음");
        assertTrue(m.projectName().contains("중소기업중앙회"), "프로젝트명(B2) 판독 실패: " + m.projectName());

        // 기준일은 반드시 월요일 (주차 = 월~금 블록)
        assertEquals(DayOfWeek.MONDAY, LocalDate.parse(m.base()).getDayOfWeek());

        assertTrue(m.summary().pProg() > 0 && m.summary().pProg() <= 1, "계획진척 이상: " + m.summary().pProg());
        assertTrue(m.summary().spi() != null, "SPI 판독 실패");

        List<Task> leaves = m.tasks().stream().filter(Task::isLeaf).toList();
        assertTrue(leaves.size() > 100, "리프 작업 수 이상: " + leaves.size());
        assertTrue(m.maxWeek() > 0, "maxWeek 계산 실패");

        for (Task t : leaves) {
            if (t.startWeek() == null) continue;
            assertTrue(t.startWeek() >= 0, t.name() + " startWeek 음수");
            assertTrue(t.endWeek() >= t.startWeek(), t.name() + " endWeek < startWeek");
        }

        // seq는 원본 행 순서 그대로 — DB 왕복 후 계층 트리를 다시 세우는 근거이므로 빠짐이 없어야 한다
        for (int i = 0; i < m.tasks().size(); i++) {
            assertEquals(i, m.tasks().get(i).seq(), "seq 연속성 깨짐");
        }
    }

    @Test
    void 대시보드_필터가_관리공정을_제외() {
        WbsService s = service();
        assertTrue(s.model().tasks().size() < s.modelAll().tasks().size(),
                "DASH_EXCLUDE(품질/일정관리/범위관리) 필터가 동작하지 않음");
    }

    @Test
    void 주차별_진척_재계산() {
        Map<String, Object> wp = service().weeklyProgress();
        List<?> rows = (List<?>) wp.get("rows");
        assertFalse(rows.isEmpty(), "주차별 진척 행 없음");

        @SuppressWarnings("unchecked")
        Map<String, Object> total = (Map<String, Object>) rows.get(0);
        assertEquals("전체", total.get("category"));
        double plan = (Double) total.get("curPlan");
        assertTrue(plan > 0 && plan <= 100, "전체 계획진척 이상: " + plan);
    }

    @Test
    void 근무일_계산() {
        // 2026-05-18(월) ~ 2026-05-22(금) = 5 근무일
        assertEquals(5, ProgressTree.networkDays(LocalDate.of(2026, 5, 18), LocalDate.of(2026, 5, 22)));
        // 주말 포함 1주도 5 근무일
        assertEquals(5, ProgressTree.networkDays(LocalDate.of(2026, 5, 18), LocalDate.of(2026, 5, 24)));
        // 시작 이전 시점이면 0
        assertEquals(0d, ProgressTree.timeRatioAsOf(
                LocalDate.of(2026, 5, 18), LocalDate.of(2026, 5, 22), LocalDate.of(2026, 5, 1)));
    }

    @Test
    void 이슈시트_헤더_매핑() {
        SheetTableReader.Table t = service().issues();
        assertTrue(t.found(), "이슈페이지 시트를 찾지 못함");
        assertTrue(t.headers().contains("이슈명"), "헤더 매핑 실패: " + t.headers());
        assertFalse(t.rows().isEmpty(), "이슈 행 없음");
    }
}
