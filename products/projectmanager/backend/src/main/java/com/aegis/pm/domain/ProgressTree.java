package com.aegis.pm.domain;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;

import com.aegis.pm.excel.Cells;

/**
 * WBS 계층 트리 + 시점별 진척률 재계산.
 * Apps Script buildProgressTree_ / nodeProgressAsOf_ / timeRatioAsOf_ / networkDays_ 이관.
 *
 * 시트의 진척률 수식은 =1/NETWORKDAYS(시작,종료) * NETWORKDAYS(시작, MIN(기준일,종료)) 형태이고
 * 상위 노드는 SUM(자식가중치 × 자식값)으로 롤업된다 — 그 계산을 그대로 재현해
 * "기준일이 특정 날짜였다면"의 값을 구한다.
 *
 * 입력은 저장소(엑셀/DB) 무관하게 Task 목록이다 — 원본이 무엇이든 seq·dep만 보존되면 같은 트리가 나온다.
 */
public class ProgressTree {

    /** 2026년 한국 공휴일 — 기준일 보정(월요일 공휴일 시 다음 평일)에만 사용 */
    private static final Set<String> HOLIDAYS_2026 = Set.of(
            "2026-01-01",
            "2026-02-16", "2026-02-17", "2026-02-18",
            "2026-03-01", "2026-03-02",
            "2026-05-01", "2026-05-05",
            "2026-05-24", "2026-05-25",
            "2026-06-03", "2026-06-06",
            "2026-07-17",
            "2026-08-15", "2026-08-17",
            "2026-09-24", "2026-09-25", "2026-09-26",
            "2026-10-03", "2026-10-05", "2026-10-09",
            "2026-12-25");

    public static class Node {
        public int dep;
        public String name = "";
        public String path = "";
        public LocalDate pStart, pEnd, aStart, aEnd;
        public double weight;
        public final List<Node> children = new ArrayList<>();

        public boolean isLeaf() { return children.isEmpty(); }
    }

    public final Node root = new Node();
    public final Node projectRoot;
    public final LocalDate base;

    /** Task 목록(원본 행 순서)으로 계층 트리를 세운다 */
    public ProgressTree(List<Task> tasks, String baseDate) {
        root.name = "전체";
        root.weight = 1;

        List<Node> stack = new ArrayList<>();
        stack.add(root);

        for (Task t : tasks) {
            Node n = new Node();
            n.dep = t.dep();
            n.name = t.name();
            n.path = t.path();
            n.pStart = parse(t.pStart());
            n.pEnd = parse(t.pEnd());
            n.aStart = parse(t.aStart());
            n.aEnd = parse(t.aEnd());
            n.weight = t.weight() == null ? 0 : t.weight();

            while (stack.size() <= n.dep) stack.add(root);
            stack.set(n.dep, n);
            while (stack.size() > n.dep + 1) stack.remove(stack.size() - 1);
            Node parent = n.dep - 1 >= 0 && n.dep - 1 < stack.size() ? stack.get(n.dep - 1) : root;
            parent.children.add(n);
        }

        this.base = parse(baseDate);
        // WBS 원본은 dep=0에 "프로젝트 전체" 행을 갖고 있어 그 행이 실질적 루트다.
        this.projectRoot = root.children.isEmpty() ? root : root.children.get(0);
    }

    private static LocalDate parse(String ymd) {
        return ymd == null || ymd.isEmpty() ? null : LocalDate.parse(ymd);
    }

    /** 노드(하위 트리 포함)의 asOf 시점 진척률 0~1. kind: plan | actual */
    public static double progressAsOf(Node node, LocalDate asOf, String kind) {
        if (node.isLeaf()) {
            LocalDate s = "plan".equals(kind) ? node.pStart : node.aStart;
            LocalDate e = "plan".equals(kind) ? node.pEnd : node.aEnd;
            return timeRatioAsOf(s, e, asOf);
        }
        double sum = 0;
        for (Node c : node.children) sum += c.weight * progressAsOf(c, asOf, kind);
        return sum;
    }

    public static double timeRatioAsOf(LocalDate start, LocalDate end, LocalDate asOf) {
        int total = networkDays(start, end);
        if (total <= 0) return 0;
        if (!asOf.isAfter(start)) return 0;
        LocalDate effEnd = asOf.isAfter(end) ? end : asOf;
        return (double) networkDays(start, effEnd) / total;
    }

    /** 주말 제외 근무일 수 (시트 NETWORKDAYS 기본 동작 — 공휴일 미차감) */
    public static int networkDays(LocalDate start, LocalDate end) {
        if (start == null || end == null || end.isBefore(start)) return 0;
        int days = 0;
        for (LocalDate d = start; !d.isAfter(end); d = d.plusDays(1)) {
            if (!isWeekend(d)) days++;
        }
        return days;
    }

    public static boolean nodeOverlaps(Node n, LocalDate from, LocalDate to, String kind) {
        LocalDate s = "plan".equals(kind) ? n.pStart : n.aStart;
        LocalDate e = "plan".equals(kind) ? n.pEnd : n.aEnd;
        if (s == null || e == null) return false;
        return !s.isAfter(to) && !e.isBefore(from);
    }

    public static List<Node> leaves(Node n) {
        if (n.isLeaf()) return List.of(n);
        List<Node> out = new ArrayList<>();
        for (Node c : n.children) out.addAll(leaves(c));
        return out;
    }

    public static boolean isWeekend(LocalDate d) {
        return d.getDayOfWeek() == DayOfWeek.SATURDAY || d.getDayOfWeek() == DayOfWeek.SUNDAY;
    }

    public static boolean isHoliday(LocalDate d) { return HOLIDAYS_2026.contains(d.format(Cells.YMD)); }

    public static LocalDate mondayOf(LocalDate d) {
        return d.minusDays((d.getDayOfWeek().getValue() - DayOfWeek.MONDAY.getValue() + 7) % 7);
    }

    /** 기준일 — 오늘이 월요일이면서 공휴일이면 다음 평일 (Apps Script effectiveAsOfDate_) */
    public static LocalDate effectiveAsOf() {
        LocalDate today = LocalDate.now();
        if (today.getDayOfWeek() == DayOfWeek.MONDAY && isHoliday(today)) {
            LocalDate d = today.plusDays(1);
            while (isWeekend(d) || isHoliday(d)) d = d.plusDays(1);
            return d;
        }
        return today;
    }

    public LocalDate weekMonday(int week) { return base.plusDays(7L * week); }

    public int weekOf(LocalDate d) { return (int) (ChronoUnit.DAYS.between(base, d) / 7); }
}
