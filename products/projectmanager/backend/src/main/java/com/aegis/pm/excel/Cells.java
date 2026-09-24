package com.aegis.pm.excel;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

/** 셀 값 해석 유틸 — Apps Script parseDate/num_/fmtD_ 이관 */
public final class Cells {

    public static final DateTimeFormatter YMD = DateTimeFormatter.ofPattern("yyyy-MM-dd");
    private static final LocalDate EXCEL_EPOCH = LocalDate.of(1899, 12, 30);

    private Cells() {}

    public static Object at(Object[] row, int col) {
        return (row != null && col >= 0 && col < row.length) ? row[col] : null;
    }

    public static String str(Object v) {
        if (v == null) return "";
        if (v instanceof LocalDate d) return d.format(YMD);
        if (v instanceof Double d) {
            // 정수형 숫자는 소수점 없이 (순번 1.0 → 1)
            return d == Math.floor(d) && !d.isInfinite()
                    ? String.valueOf(d.longValue()) : String.valueOf(d);
        }
        return String.valueOf(v).trim();
    }

    /** 숫자 아니면 null (Apps Script num_ 대응) */
    public static Double num(Object v) {
        if (v instanceof Double d) return d;
        if (v instanceof String s) {
            try { return Double.parseDouble(s.trim()); } catch (NumberFormatException e) { return null; }
        }
        return null;
    }

    /**
     * 날짜 파싱 — Apps Script parseDate() 이관.
     * 날짜 셀 / 엑셀 시리얼 숫자 / yyyy-MM-dd(구분자 - / .) / "yyyy년 M월 d일" 지원.
     * 계약(yyyy-MM-dd) 위반 문자열은 null (비계약 날짜 누출 방지).
     */
    public static LocalDate date(Object v) {
        if (v instanceof LocalDate d) return d;
        if (v instanceof Double serial) return EXCEL_EPOCH.plusDays(serial.longValue());
        if (v instanceof String s) {
            String t = s.trim();
            String[] p = t.split("[-/.]");
            if (p.length == 3) {
                try {
                    return LocalDate.of(Integer.parseInt(p[0].trim()),
                            Integer.parseInt(p[1].trim()), Integer.parseInt(p[2].trim()));
                } catch (Exception ignore) { /* 아래 한글 패턴으로 재시도 */ }
            }
            var m = java.util.regex.Pattern.compile("(\\d{4})년\\s*(\\d{1,2})월\\s*(\\d{1,2})일").matcher(t);
            if (m.find()) {
                return LocalDate.of(Integer.parseInt(m.group(1)),
                        Integer.parseInt(m.group(2)), Integer.parseInt(m.group(3)));
            }
        }
        return null;
    }

    public static String fmt(LocalDate d) { return d == null ? "" : d.format(YMD); }
}
