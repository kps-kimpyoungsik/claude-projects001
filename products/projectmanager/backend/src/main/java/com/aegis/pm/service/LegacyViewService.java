package com.aegis.pm.service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Service;

import com.aegis.pm.domain.ProgressTree;
import com.aegis.pm.domain.Tasks;
import com.aegis.pm.domain.WbsModel;
import com.aegis.pm.excel.Cells;
import com.aegis.pm.repo.WbsRepository;

/**
 * Apps Script 원본 화면이 기대하는 JSON 형태를 그대로 만들어주는 서비스.
 *
 * 화면(원본 HTML/JS)을 고치지 않고 그대로 쓰기 위해, 응답 키 이름·중첩 구조를
 * `getWeeklyArchiveJson()` / `getWeekLiveJson()` 원본과 1:1로 맞춘다.
 */
@Service
public class LegacyViewService {

    /** 주차별 리포트 시작 주차 — 원본 WEEKLY_ARCHIVE_START_WEEK_ */
    private static final int ARCHIVE_START_WEEK = 7;
    /** 대분류 대신 중분류로 펼칠 대상 — 원본 WEEKLY_PROGRESS_EXPAND_BIGS_ */
    private static final List<String> EXPAND_BIGS = List.of("관리", "업무수행");
    /** 최하위 리프까지 펼쳐 표시할 중분류 — 원본 WEEKLY_ARCHIVE_DEEP_DIVE_MID_ */
    private static final String DEEP_DIVE_MID = "구현";

    private final WbsRepository repo;

    public LegacyViewService(WbsRepository repo) {
        this.repo = repo;
    }

    /** getWeeklyArchiveJson() 이관 */
    public Map<String, Object> weeklyArchive() {
        WbsModel m = repo.model();
        ProgressTree tree = new ProgressTree(m.tasks(), m.base());
        LocalDate asOf = ProgressTree.effectiveAsOf();

        int maxWeek = m.maxWeek();
        int curWeek = Math.max(0, tree.weekOf(asOf));

        // 오늘 주차부터 미래는 오름차순, 지난 주차는 뒤로(최근 것 먼저) — 원본 정렬 관례
        List<Integer> order = new ArrayList<>();
        for (int w = Math.max(curWeek, ARCHIVE_START_WEEK); w <= maxWeek; w++) order.add(w);
        for (int w = Math.min(curWeek, maxWeek) - 1; w >= ARCHIVE_START_WEEK; w--) order.add(w);

        List<Map<String, Object>> weeks = new ArrayList<>();
        for (int w : order) weeks.add(weekBody(tree, w, asOf, false));

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("startWeek", ARCHIVE_START_WEEK);
        out.put("maxWeek", maxWeek);
        out.put("curWeek", curWeek);
        out.put("weeks", weeks);
        out.put("serverTime", now());
        return out;
    }

    /**
     * getWeekSnapshotOrLive(week) 이관.
     * 원본은 시트의 기준일 셀을 잠시 바꿔 시트가 재계산한 값을 읽었지만,
     * 여기서는 같은 수식을 그대로 재현하는 ProgressTree로 계산한다(결과 동일, 원본 훼손 없음).
     */
    public Map<String, Object> week(int weekNum) {
        WbsModel m = repo.model();
        ProgressTree tree = new ProgressTree(m.tasks(), m.base());
        return weekBody(tree, weekNum, ProgressTree.effectiveAsOf(), true);
    }

    private Map<String, Object> weekBody(ProgressTree tree, int week, LocalDate asOf, boolean single) {
        LocalDate curMon = tree.weekMonday(week);
        LocalDate curFri = curMon.plusDays(4);
        LocalDate nextMon = curMon.plusDays(7);
        LocalDate nextFri = nextMon.plusDays(4);
        // 실적은 미래를 앞당겨 계상하지 않는다 — 지난 주는 그 주 금요일, 진행 중이면 오늘까지
        LocalDate actualAsOf = curFri.isBefore(asOf) ? curFri : asOf;

        List<Map<String, Object>> groups = new ArrayList<>();
        for (ProgressTree.Node g : groupNodes(tree)) {
            List<Map<String, Object>> curItems = bullets(g, curMon, curFri, true, actualAsOf);
            List<Map<String, Object>> nextItems = bullets(g, nextMon, nextFri, false, actualAsOf);
            if (curItems.isEmpty() && nextItems.isEmpty()) continue;
            Map<String, Object> gm = new LinkedHashMap<>();
            gm.put("label", g.name);
            gm.put("curItems", curItems);
            gm.put("nextItems", nextItems);
            groups.add(gm);
        }

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("week", week);
        if (single) {
            out.put("source", "live");
            out.put("hasSnapshot", false);
        }
        out.put("asOfDate", curFri.format(Cells.YMD));
        out.put("curRange", Map.of("start", curMon.format(Cells.YMD), "end", curFri.format(Cells.YMD)));
        out.put("nextRange", Map.of("start", nextMon.format(Cells.YMD), "end", nextFri.format(Cells.YMD)));
        out.put("groups", groups);
        out.put("notes", notes(curMon, curFri));
        if (single) {
            out.put("notesEditable", "");
            out.put("serverTime", now());
        }
        return out;
    }

    /** 대분류(또는 EXPAND_BIGS의 중분류) 그룹 목록 — 원본 buildWeeklyGroupDefs_ */
    private List<ProgressTree.Node> groupNodes(ProgressTree tree) {
        List<ProgressTree.Node> defs = new ArrayList<>();
        for (ProgressTree.Node big : tree.projectRoot.children) {
            if (EXPAND_BIGS.contains(big.name)) defs.addAll(big.children);
            else defs.add(big);
        }
        return defs;
    }

    /** 원본 groupBullets_ — 실적 항목은 "{이름} {진척률}%" + 상태, 계획 항목은 이름만 */
    private List<Map<String, Object>> bullets(ProgressTree.Node node, LocalDate from, LocalDate to,
                                              boolean withStatus, LocalDate actualAsOf) {
        List<ProgressTree.Node> units = DEEP_DIVE_MID.equals(node.name)
                ? ProgressTree.leaves(node) : node.children;
        List<Map<String, Object>> out = new ArrayList<>();
        for (ProgressTree.Node n : units) {
            if (!ProgressTree.nodeOverlaps(n, from, to, "plan")) continue;
            Map<String, Object> item = new LinkedHashMap<>();
            if (withStatus) {
                double prog = ProgressTree.progressAsOf(n, actualAsOf, "actual") * 100;
                item.put("text", n.name + " " + String.format("%.1f", prog) + "%");
                item.put("status", prog >= 100 - 1e-6 ? "완료" : "진행");
            } else {
                item.put("text", n.name);
            }
            item.put("due", n.pEnd == null ? "" : n.pEnd.format(Cells.YMD));
            out.add(item);
        }
        return out;
    }

    /** 해당 주 계획 구간에 걸친 리프의 비고(중복 제거) */
    private List<String> notes(LocalDate from, LocalDate to) {
        LinkedHashSet<String> seen = new LinkedHashSet<>();
        WbsModel m = repo.model();
        for (var t : m.tasks()) {
            if (!t.isLeaf() || t.note() == null || t.note().isBlank()) continue;
            if (!Tasks.dashKeep(t)) continue;
            if (t.pStart() == null || t.pStart().isEmpty() || t.pEnd() == null || t.pEnd().isEmpty()) continue;
            LocalDate s = LocalDate.parse(t.pStart());
            LocalDate e = LocalDate.parse(t.pEnd());
            if (s.isAfter(to) || e.isBefore(from)) continue;
            seen.add(t.note().trim());
        }
        return new ArrayList<>(seen);
    }

    private static String now() {
        return LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
    }
}
