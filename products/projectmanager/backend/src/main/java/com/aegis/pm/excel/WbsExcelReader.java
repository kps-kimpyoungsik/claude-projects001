package com.aegis.pm.excel;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;

import org.springframework.stereotype.Component;

import com.aegis.pm.config.WbsProperties;
import com.aegis.pm.domain.Summary;
import com.aegis.pm.domain.Task;
import com.aegis.pm.domain.WbsModel;

/**
 * WBS_Raw → 공통 모델 파싱. Apps Script buildModel_() 1:1 이관.
 *
 * 컬럼 좌표(0-based)와 데이터 시작행은 Apps Script CONFIG를 그대로 옮겼다 —
 * 시트 레이아웃이 계약이므로 하드코딩이 아니라 이관 대상 상수다.
 */
@Component
public class WbsExcelReader {

    // CONFIG.COL 이관 (0-based)
    private static final int COL_NO = 1, COL_DEP = 3, COL_NAME_BASE = 4;
    private static final int COL_P_START = 12, COL_P_END = 13, COL_OWNER = 14, COL_PART = 15, COL_P_PROG = 16;
    private static final int COL_A_START = 17, COL_A_END = 18, COL_A_PROG = 19, COL_WEIGHT = 20;
    private static final int COL_NOTE = 25;
    private static final int DATA_START_ROW0 = 5;
    // CONFIG.SUMMARY 이관 — 2행(0-based 1)의 계획/실적/SPI/기준일자
    private static final int SUM_ROW = 1, SUM_P = 19, SUM_A = 21, SUM_SPI = 23, SUM_ASOF = 17;
    private static final LocalDate PROJECT_START_FALLBACK = LocalDate.of(2026, 5, 15);

    private final ExcelSource source;
    private final WbsProperties props;

    public WbsExcelReader(ExcelSource source, WbsProperties props) {
        this.source = source;
        this.props = props;
    }

    public WbsModel read() {
        return parse(source.grid(props.getRawSheet(), "WBS_Raw", "WEB_Raw", "Raw"));
    }

    /** 업로드된 임의 파일에서 읽기 — 설정된 원본 파일을 건드리지 않는다 */
    public WbsModel read(java.io.File file) {
        return parse(com.aegis.pm.excel.Workbooks.grid(file, props.getRawSheet(), "WBS_Raw", "WEB_Raw", "Raw"));
    }

    private WbsModel parse(Object[][] data) {
        if (data == null) throw new IllegalStateException("원본 시트(WBS_Raw 등)를 찾을 수 없습니다.");

        Object[] sumRow = data.length > SUM_ROW ? data[SUM_ROW] : new Object[0];
        Summary summary = new Summary(
                Cells.num(Cells.at(sumRow, SUM_P)),
                Cells.num(Cells.at(sumRow, SUM_A)),
                Cells.num(Cells.at(sumRow, SUM_SPI)),
                Cells.fmt(Cells.date(Cells.at(sumRow, SUM_ASOF))));

        String projectName = Cells.str(Cells.at(data.length > 1 ? data[1] : null, 1));

        // 기준일 = 전체 최소 계획시작일 → 그 주 월요일 (주차 = 월~금 블록, 하드코딩 금지)
        LocalDate base = null;
        for (int i = DATA_START_ROW0; i < data.length; i++) {
            LocalDate ps = Cells.date(Cells.at(data[i], COL_P_START));
            if (ps != null && (base == null || ps.isBefore(base))) base = ps;
        }
        if (base == null) base = PROJECT_START_FALLBACK;
        base = mondayOf(base);

        List<Object[]> rows = new ArrayList<>();
        for (int i = DATA_START_ROW0; i < data.length; i++) rows.add(data[i]);

        List<Task> tasks = new ArrayList<>();
        List<String> pathStack = new ArrayList<>();
        int maxWeek = 0;

        for (int i = 0; i < rows.size(); i++) {
            Object[] row = rows.get(i);
            Double depNum = Cells.num(Cells.at(row, COL_DEP));
            if (depNum == null) continue;
            int dep = depNum.intValue();

            String name = Cells.str(Cells.at(row, COL_NAME_BASE + dep));
            if (name.isEmpty()) continue;

            while (pathStack.size() <= dep) pathStack.add("");
            pathStack.set(dep, name);
            while (pathStack.size() > dep + 1) pathStack.remove(pathStack.size() - 1);
            String path = String.join(" > ", pathStack.subList(Math.min(1, pathStack.size()), pathStack.size()));

            // 다음 유효행의 dep이 현재 이하이면 리프
            boolean isLeaf = true;
            for (int j = i + 1; j < rows.size(); j++) {
                Double nd = Cells.num(Cells.at(rows.get(j), COL_DEP));
                if (nd == null) continue;
                isLeaf = nd.intValue() <= dep;
                break;
            }

            LocalDate pStart = Cells.date(Cells.at(row, COL_P_START));
            LocalDate pEnd = Cells.date(Cells.at(row, COL_P_END));
            Integer week = null, startWeek = null, endWeek = null;
            if (pStart != null) {
                startWeek = (int) Math.max(0, ChronoUnit.DAYS.between(base, pStart) / 7);
                week = startWeek;
                LocalDate endRef = pEnd != null ? pEnd : pStart;
                endWeek = (int) (ChronoUnit.DAYS.between(base, endRef) / 7);
                if (endWeek < startWeek) endWeek = startWeek;
            }

            Double aProg = Cells.num(Cells.at(row, COL_A_PROG));
            Task t = new Task(
                    tasks.size(),
                    numOrNull(Cells.at(row, COL_NO)),
                    dep, name, path,
                    get(pathStack, 1), get(pathStack, 2), get(pathStack, 3),
                    Cells.fmt(pStart), Cells.fmt(pEnd),
                    Cells.str(Cells.at(row, COL_OWNER)), Cells.str(Cells.at(row, COL_PART)),
                    Cells.num(Cells.at(row, COL_P_PROG)),
                    Cells.fmt(Cells.date(Cells.at(row, COL_A_START))),
                    Cells.fmt(Cells.date(Cells.at(row, COL_A_END))),
                    aProg,
                    Cells.num(Cells.at(row, COL_WEIGHT)),
                    Cells.str(Cells.at(row, COL_NOTE)),
                    week, startWeek, endWeek, isLeaf, statusOf(aProg));
            tasks.add(t);

            // maxWeek는 DASH_EXCLUDE 필터 이전 전체 기준 (현재시점 선이 축소 주차수로 잘못 clamp되는 것 방지)
            if (isLeaf && endWeek != null && endWeek > maxWeek) maxWeek = endWeek;
        }

        String serverTime = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
        String asOf = (summary.asOf() == null || summary.asOf().isEmpty())
                ? LocalDate.now().format(Cells.YMD) : summary.asOf();

        return new WbsModel(summary, tasks, Cells.fmt(base), maxWeek, projectName, asOf, serverTime);
    }

    private static String get(List<String> stack, int i) {
        return i < stack.size() && stack.get(i) != null ? stack.get(i) : "";
    }

    private static Integer numOrNull(Object v) {
        Double d = Cells.num(v);
        return d == null ? null : d.intValue();
    }

    /** Apps Script statusOf_ 이관 */
    private static String statusOf(Double aProg) {
        if (aProg != null) {
            if (aProg >= 1) return "완료";
            if (aProg > 0) return "진행중";
        }
        return "대기";
    }

    /** 그 주 월요일 (Apps Script mondayOf_) */
    private static LocalDate mondayOf(LocalDate d) {
        return d.minusDays((d.getDayOfWeek().getValue() - DayOfWeek.MONDAY.getValue() + 7) % 7);
    }
}
