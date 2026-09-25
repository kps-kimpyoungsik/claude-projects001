package com.aegis.pm.engine;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 정제 계획 — 프로파일과 역할에서 <b>무엇을 고치면 좋은지</b>를 찾고(plan), 원본을 두고 새 표로 만든다(apply).
 * 규칙은 전부 값의 성질에서 나온다 — "이 분야라서"가 아니라 "이 열의 92%가 숫자인데 8%가 아니라서".
 *
 * <pre>
 *   DROP_EMPTY_COLUMN   값이 하나도 없는 열
 *   NORMALIZE_NULL      "-" "N/A" 같은 결측 표기 → 빈 값
 *   TRIM_SPACE          앞뒤·연속 공백
 *   DATE_SERIAL_TO_ISO  시간 열의 엑셀 일련번호 → yyyy-MM-dd
 *   DATE_FORMAT_UNIFY   시간 열의 2026.9.1 · 2026/09/01 → 2026-09-01
 *   NUMBER_UNFORMAT     수치 열의 "1,234" → 1234
 *   NUMBER_OUTLIER      수치 열의 IQR 3배 밖 값 (표시만 — 고치지 않는다)
 *   NUMBER_RESIDUE      수치 열인데 숫자가 아닌 값 (표시만)
 *   DEDUPE_ROWS         완전히 같은 행
 * </pre>
 */
public final class RefinePlanner {

    private RefinePlanner() {}

    public record Op(String op, String column, int cells, String detail, boolean applies) {}

    private static final Pattern DATE = Pattern.compile("^(\\d{4})[-./](\\d{1,2})[-./](\\d{1,2})(\\D.*)?$");

    public static List<Op> plan(List<String> headers, List<Map<String, String>> rows, Map<String, String> roles) {
        List<Op> ops = new ArrayList<>();
        for (String h : headers) {
            List<String> col = column(rows, h);
            DataProfiler.Profile p = DataProfiler.profile(col);
            String role = roles.getOrDefault(h, "text");
            if (p.filled() == 0 && p.nullish() == 0) { ops.add(new Op("DROP_EMPTY_COLUMN", h, rows.size(), "값 0", true)); continue; }
            if (p.nullish() > 0) ops.add(new Op("NORMALIZE_NULL", h, p.nullish(), "결측 표기 → 빈 값", true));
            if (p.padded() > 0) ops.add(new Op("TRIM_SPACE", h, p.padded(), "앞뒤·연속 공백", true));
            if ("time".equals(role)) {
                int serial = 0, fmt = 0;
                for (String v : col) {
                    if (v == null || v.isBlank()) continue;
                    if (isSerial(v)) serial++;
                    else { Matcher m = DATE.matcher(v.trim()); if (m.matches() && !v.trim().equals(iso(m))) fmt++; }
                }
                if (serial > 0) ops.add(new Op("DATE_SERIAL_TO_ISO", h, serial, "엑셀 일련번호 → yyyy-MM-dd", true));
                if (fmt > 0) ops.add(new Op("DATE_FORMAT_UNIFY", h, fmt, "날짜 표기 통일 → yyyy-MM-dd", true));
            }
            if ("measure".equals(role)) {
                if (p.commaNumbers() > 0) ops.add(new Op("NUMBER_UNFORMAT", h, p.commaNumbers(), "쉼표·% 제거", true));
                double[] xs = col.stream().filter(DataProfiler::isNumber).mapToDouble(DataProfiler::parse).sorted().toArray();
                int residue = (int) col.stream().filter(v -> v != null && !v.isBlank() && !DataProfiler.isNullish(v) && !DataProfiler.isNumber(v)).count();
                if (residue > 0) ops.add(new Op("NUMBER_RESIDUE", h, residue, "수치 열인데 숫자가 아닌 값", false));
                if (xs.length >= 8) {
                    double q1 = xs[xs.length / 4], q3 = xs[(3 * xs.length) / 4], iqr = q3 - q1;
                    if (iqr > 0) {
                        long out = Arrays.stream(xs).filter(x -> x < q1 - 3 * iqr || x > q3 + 3 * iqr).count();
                        if (out > 0) ops.add(new Op("NUMBER_OUTLIER", h, (int) out, String.format("IQR 3배 밖 (%.4g~%.4g)", q1 - 3 * iqr, q3 + 3 * iqr), false));
                    }
                }
            }
        }
        Set<String> seen = new HashSet<>();
        int dup = 0;
        for (Map<String, String> r : rows) if (!seen.add(r.toString())) dup++;
        if (dup > 0) ops.add(new Op("DEDUPE_ROWS", null, dup, "완전히 같은 행", true));
        return ops;
    }

    /** 사람 결정 — true 면 그 (op, 열, 원본 행)의 정제를 하지 않는다 */
    @FunctionalInterface
    public interface Keep {
        boolean skip(String op, String col, int row);
        Keep NONE = (op, col, row) -> false;
    }

    /** 결정 키 "op|열|행" — 열 "" = 모든 열, 행 -1 = 모든 행 */
    public static Keep keep(List<String> keys) {
        Set<String> k = new HashSet<>(keys);
        if (k.isEmpty()) return Keep.NONE;
        return (op, col, row) -> {
            String c = col == null ? "" : col;
            return k.contains(op + "|" + c + "|" + row) || k.contains(op + "|" + c + "|-1")
                    || k.contains(op + "||" + row) || k.contains(op + "||-1");
        };
    }

    public static Map<String, Object> apply(List<String> headers, List<Map<String, String>> rows, List<Op> ops) {
        return apply(headers, rows, ops, Keep.NONE);
    }

    /**
     * 계획 중 applies=true 인 것만 적용한 새 행 목록 — 원본은 건드리지 않는다.
     * 결과의 "traces" 는 사라지거나 바뀐 값 전부(원본 행 번호 · 이전 값 → 이후 값).
     */
    public static Map<String, Object> apply(List<String> headers, List<Map<String, String>> rows, List<Op> ops, Keep keep) {
        Set<String> drop = new HashSet<>(), nulls = new HashSet<>(), trim = new HashSet<>(), serial = new HashSet<>(),
                fmt = new HashSet<>(), unformat = new HashSet<>();
        boolean dedupe = false;
        for (Op o : ops) {
            if (!o.applies()) continue;
            switch (o.op()) {
                case "DROP_EMPTY_COLUMN" -> { if (!keep.skip(o.op(), o.column(), -1)) drop.add(o.column()); }
                case "NORMALIZE_NULL" -> nulls.add(o.column());
                case "TRIM_SPACE" -> trim.add(o.column());
                case "DATE_SERIAL_TO_ISO" -> serial.add(o.column());
                case "DATE_FORMAT_UNIFY" -> fmt.add(o.column());
                case "NUMBER_UNFORMAT" -> unformat.add(o.column());
                case "DEDUPE_ROWS" -> dedupe = true;
                default -> { }
            }
        }
        List<String> outHeaders = headers.stream().filter(h -> !drop.contains(h)).toList();
        List<Map<String, String>> out = new ArrayList<>();
        List<TraceStore.Trace> traces = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        for (int i = 0; i < rows.size(); i++) {
            Map<String, String> r = rows.get(i);
            Map<String, String> c = new LinkedHashMap<>();
            for (String h : outHeaders) {
                String v = r.get(h);
                if (v == null) continue;
                if (trim.contains(h) && !keep.skip("TRIM_SPACE", h, i)) v = step(traces, "TRIM_SPACE", i, h, v, v.trim().replaceAll("\\s{2,}", " "));
                if (nulls.contains(h) && DataProfiler.isNullish(v) && !keep.skip("NORMALIZE_NULL", h, i)) {
                    traces.add(new TraceStore.Trace("REFINE", "NORMALIZE_NULL", i, h, v, null));
                    continue;
                }
                if (serial.contains(h) && isSerial(v) && !keep.skip("DATE_SERIAL_TO_ISO", h, i))
                    v = step(traces, "DATE_SERIAL_TO_ISO", i, h, v, LocalDate.of(1899, 12, 30).plusDays((long) DataProfiler.parse(v)).toString());
                if (fmt.contains(h) && !keep.skip("DATE_FORMAT_UNIFY", h, i)) { Matcher m = DATE.matcher(v.trim()); if (m.matches()) v = step(traces, "DATE_FORMAT_UNIFY", i, h, v, iso(m)); }
                if (unformat.contains(h) && DataProfiler.isNumber(v) && !keep.skip("NUMBER_UNFORMAT", h, i))
                    v = step(traces, "NUMBER_UNFORMAT", i, h, v, v.trim().replace(",", "").replace("%", ""));
                if (!v.isEmpty()) c.put(h, v);
            }
            if (c.isEmpty()) continue;
            if (dedupe && !seen.add(c.toString()) && !keep.skip("DEDUPE_ROWS", null, i)) {
                traces.add(new TraceStore.Trace("REFINE", "DEDUPE_ROWS", i, null, r.toString(), null));
                continue;
            }
            out.add(c);
        }
        Map<String, Object> res = new LinkedHashMap<>();
        res.put("headers", outHeaders);
        res.put("rows", out);
        res.put("traces", traces);
        return res;
    }

    /** 값이 실제로 바뀐 경우만 이력에 남긴다 */
    private static String step(List<TraceStore.Trace> traces, String op, int row, String col, String before, String after) {
        if (!after.equals(before)) traces.add(new TraceStore.Trace("REFINE", op, row, col, before, after));
        return after;
    }

    static List<String> column(List<Map<String, String>> rows, String h) {
        List<String> col = new ArrayList<>(rows.size());
        for (Map<String, String> r : rows) col.add(r.get(h));
        return col;
    }

    private static boolean isSerial(String v) {
        if (!DataProfiler.isNumber(v)) return false;
        double d = DataProfiler.parse(v);
        return d >= DataProfiler.SERIAL_MIN && d <= DataProfiler.SERIAL_MAX && d == Math.floor(d);
    }

    private static String iso(Matcher m) {
        try {
            return LocalDate.of(Integer.parseInt(m.group(1)), Integer.parseInt(m.group(2)), Integer.parseInt(m.group(3))).toString();
        } catch (RuntimeException e) {
            return m.group(0);
        }
    }
}
