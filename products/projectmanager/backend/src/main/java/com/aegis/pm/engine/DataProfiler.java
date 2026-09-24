package com.aegis.pm.engine;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * 범용 규칙 발견 엔진 — 1층: 값 목록 하나를 <b>특징 벡터</b>로 바꾼다. 도메인 단어를 쓰지 않는다.
 *
 * <p>무엇을 담는 컬럼인지(날짜·수치·식별자·범주·본문)는 이름이 아니라 <b>값의 분포</b>가 말한다.
 * 이 벡터 위에서 역할 추정(RoleModel)·정제 제안(RefinePlanner)·헤더 탐지(HeaderDetector)가 돈다.
 */
public final class DataProfiler {

    private DataProfiler() {}

    /** 결측으로 보는 표기 — 구두점·공백뿐인 값 + 흔한 결측 리터럴(도메인 무관) */
    private static final Pattern NULLISH = Pattern.compile("^[\\p{Punct}\\s]*$|^(?i)(n/?a|null|none|nan|nil)$");
    private static final Pattern NUMBER = Pattern.compile("^[+-]?(\\d{1,3}(,\\d{3})+|\\d+)(\\.\\d+)?%?$");
    private static final Pattern DATE = Pattern.compile("^(\\d{4})[-./](\\d{1,2})[-./](\\d{1,2})(\\D.*)?$");
    private static final Pattern TOKEN = Pattern.compile("PII-[0-9a-f]{12}");
    /** 엑셀 날짜 일련번호로 볼 수 있는 범위 — 1954-10 ~ 2119-01 */
    static final double SERIAL_MIN = 20000, SERIAL_MAX = 80000;

    public record Profile(
            int n,                 // 행 수(빈 칸 포함)
            int filled,            // 값이 있는 칸
            int distinct,          // 고유값 수(채워진 칸 기준)
            double fill,           // filled / n
            double distinctRatio,  // distinct / filled
            double numericRatio,   // 숫자로 읽히는 비율
            double dateRatio,      // 날짜 문자열 비율
            double serialRatio,    // 엑셀 일련번호로 볼 수 있는 정수 비율
            double tokenRatio,     // 가명 토큰(PII-…) 비율 — 개인정보 파이프라인이 붙인 표식
            double avgLen,
            int maxLen,
            double entropy,        // 정규화 엔트로피 0~1 — 값이 고르게 퍼질수록 1
            int nullish,           // 결측 표기 칸 수(값은 있지만 사실상 빈 것)
            int padded,            // 앞뒤·중복 공백이 있는 칸 수
            int commaNumbers,      // "1,234" 처럼 쉼표 숫자 칸 수
            double avgWords,       // 공백으로 나눈 평균 낱말 수 — 코드·이름은 1~2, 문장은 여럿
            boolean sequential) {  // 전부 정수이고 최댓값-최솟값+1 ≈ 개수 — 순번

        public double[] vector() {
            return new double[] { fill, distinctRatio, numericRatio, dateRatio, serialRatio, tokenRatio,
                    Math.min(1, avgLen / 60.0), entropy, Math.min(1, avgWords / 10.0), sequential ? 1 : 0 };
        }
    }

    public static Profile profile(List<String> values) {
        int n = values.size(), filled = 0, num = 0, date = 0, serial = 0, token = 0, nullish = 0, padded = 0, comma = 0;
        long len = 0, words = 0;
        int maxLen = 0, ints = 0;
        double lo = Double.MAX_VALUE, hi = -Double.MAX_VALUE;
        Map<String, Integer> freq = new HashMap<>();
        for (String raw : values) {
            if (raw == null || raw.isEmpty()) continue;
            if (!raw.equals(raw.trim()) || raw.contains("  ")) padded++;
            String v = raw.trim();
            if (NULLISH.matcher(v).matches()) { nullish++; continue; }
            filled++;
            freq.merge(v, 1, Integer::sum);
            len += v.length();
            words += v.split("\\s+").length;
            maxLen = Math.max(maxLen, v.length());
            if (TOKEN.matcher(v).find()) token++;
            if (DATE.matcher(v).matches()) date++;
            if (NUMBER.matcher(v).matches()) {
                num++;
                if (v.indexOf(',') >= 0) comma++;
                double d = parse(v);
                if (d >= SERIAL_MIN && d <= SERIAL_MAX && d == Math.floor(d)) serial++;
                if (d == Math.floor(d)) { ints++; lo = Math.min(lo, d); hi = Math.max(hi, d); }
            }
        }
        double f = n == 0 ? 0 : (double) filled / n;
        double h = 0;
        for (int c : freq.values()) {
            double p = (double) c / filled;
            h -= p * Math.log(p);
        }
        double hn = freq.size() <= 1 ? 0 : h / Math.log(freq.size());
        return new Profile(n, filled, freq.size(), f, filled == 0 ? 0 : (double) freq.size() / filled,
                ratio(num, filled), ratio(date, filled), ratio(serial, filled), ratio(token, filled),
                filled == 0 ? 0 : (double) len / filled, maxLen, hn, nullish, padded, comma,
                filled == 0 ? 0 : (double) words / filled,
                filled >= 3 && ints == filled && (hi - lo + 1) <= filled * 1.5);
    }

    public static boolean isNullish(String v) {
        return v != null && NULLISH.matcher(v.trim()).matches();
    }

    public static boolean isNumber(String v) {
        return v != null && NUMBER.matcher(v.trim()).matches();
    }

    public static boolean isDate(String v) {
        return v != null && DATE.matcher(v.trim()).matches();
    }

    public static double parse(String v) {
        try {
            return Double.parseDouble(v.trim().replace(",", "").replace("%", ""));
        } catch (RuntimeException e) {
            return Double.NaN;
        }
    }

    /** 셀 하나의 타입 — 헤더 탐지가 행 간 타입 대비를 볼 때 쓴다 */
    public static char kind(String v) {
        if (v == null || v.isBlank() || isNullish(v)) return '_';
        if (isDate(v)) return 'D';
        if (isNumber(v)) return 'N';
        return 'S';
    }

    private static double ratio(int a, int b) {
        return b == 0 ? 0 : (double) a / b;
    }
}
