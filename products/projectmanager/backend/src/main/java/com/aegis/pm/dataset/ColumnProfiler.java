package com.aegis.pm.dataset;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * 컬럼 값에서 타입을 추론한다 — 대시보드 자동 초안의 근거다.
 *
 *   number   : 값 대부분이 숫자      → 합계·평균 KPI
 *   date     : 값 대부분이 날짜      → 기간 추이(trend)
 *   category : 서로 다른 값이 적음   → 분포(bar·donut)
 *   text     : 그 외                 → 표에만 표시
 */
final class ColumnProfiler {

    /** 분포 차트로 의미가 있는 고유값 상한 — 이보다 많으면 자유 텍스트로 본다 */
    private static final int CATEGORY_MAX_DISTINCT = 20;
    /** 타입으로 인정할 최소 비율 (빈 값 제외한 값 중) */
    private static final double TYPE_RATIO = 0.7;

    private static final Pattern NUMBER = Pattern.compile("^-?[0-9,]+(\\.[0-9]+)?%?$");
    private static final Pattern DATE = Pattern.compile("^\\d{4}[-/.]\\d{1,2}([-/.]\\d{1,2})?");

    private ColumnProfiler() {}

    /** dataset_column INSERT 파라미터 순서 그대로 반환 */
    static Object[] profile(String datasetId, int colNo, String name, List<Map<String, String>> rows) {
        LinkedHashSet<String> distinct = new LinkedHashSet<>();
        int nulls = 0, numeric = 0, dates = 0, total = 0;
        double sum = 0;
        String min = null, max = null;
        Double minNum = null, maxNum = null;

        for (Map<String, String> r : rows) {
            String v = r.get(name);
            if (v == null || v.isBlank()) { nulls++; continue; }
            total++;
            if (distinct.size() <= CATEGORY_MAX_DISTINCT + 1) distinct.add(v);

            Double num = toNumber(v);
            if (num != null) {
                numeric++;
                sum += num;
                if (minNum == null || num < minNum) minNum = num;
                if (maxNum == null || num > maxNum) maxNum = num;
            }
            if (DATE.matcher(v).find()) {
                dates++;
                String d = v.substring(0, Math.min(10, v.length()));
                if (min == null || d.compareTo(min) < 0) min = d;
                if (max == null || d.compareTo(max) > 0) max = d;
            }
        }

        String type;
        if (total == 0) {
            type = "text";
        } else if ((double) dates / total >= TYPE_RATIO) {
            type = "date";
        } else if ((double) numeric / total >= TYPE_RATIO) {
            type = "number";
            min = minNum == null ? null : trim(minNum);
            max = maxNum == null ? null : trim(maxNum);
        } else if (distinct.size() <= CATEGORY_MAX_DISTINCT) {
            type = "category";
            min = null;
            max = null;
        } else {
            type = "text";
            min = null;
            max = null;
        }

        return new Object[]{datasetId, colNo, name, type,
                Math.min(distinct.size(), CATEGORY_MAX_DISTINCT + 1), nulls, min, max,
                "number".equals(type) ? sum : null};
    }

    /** "1,234" · "85%" 같은 표기도 숫자로 본다 */
    static Double toNumber(String v) {
        if (v == null) return null;
        String s = v.trim().replace(",", "");
        boolean pct = s.endsWith("%");
        if (pct) s = s.substring(0, s.length() - 1);
        if (!NUMBER.matcher(v.trim()).matches()) return null;
        try {
            return Double.parseDouble(s);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static String trim(double d) {
        return d == Math.floor(d) && !Double.isInfinite(d)
                ? String.valueOf((long) d) : String.valueOf(Math.round(d * 100) / 100d);
    }
}
