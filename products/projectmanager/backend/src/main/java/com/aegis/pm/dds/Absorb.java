package com.aegis.pm.dds;

import java.util.List;
import java.util.Locale;
import java.util.regex.Pattern;

/**
 * 흡수 경계 — 어디까지 사전에 넣을 것인가 (05 §3.2).
 *
 * <p>이 클래스가 이 Phase 의 SAFETY 지점이다. 경계가 느슨하면 사전이 개인정보 저장소가 된다.
 * 그래서 판정은 "넣어도 되는 이유"가 아니라 <b>"빼야 하는 이유"</b>를 찾는 방향으로 돈다 —
 * 이유가 하나라도 잡히면 흡수하지 않는다(기본값 = 제외).
 *
 * <p>전부 순수 함수다. DB·Spring 없이 테스트된다.
 */
public final class Absorb {

    /** 용어 길이 상한 — 이보다 길면 용어가 아니라 내용이다 */
    private static final int MAX_LEN = 30;

    /** 공백 상한 — 넘으면 문장이다 */
    private static final int MAX_SPACES = 3;

    private static final Pattern NUMERIC = Pattern.compile("^-?[0-9,]+(\\.[0-9]+)?\\s*[%원일건명개]?$");
    private static final Pattern DATE = Pattern.compile("^\\d{4}[-/.]\\d{1,2}([-/.]\\d{1,2})?");
    private static final Pattern FILE_PATH = Pattern.compile(
            ".*([/\\\\]|\\.(xlsx|xls|csv|pdf|png|jpe?g|zip|txt|json))\\s*$", Pattern.CASE_INSENSITIVE);
    private static final Pattern EMAIL = Pattern.compile(".*@.*\\..*");
    private static final Pattern PHONE = Pattern.compile("^\\d{2,4}[-.]?\\d{3,4}[-.]?\\d{4}$");
    private static final Pattern RRN = Pattern.compile("^\\d{6}-?\\d{7}$");
    private static final Pattern SECRETISH = Pattern.compile("^[A-Za-z0-9+/=_-]{32,}$");

    /** 컬럼명이 이걸 품으면 그 컬럼의 <b>값</b>은 흡수하지 않는다 (필드명만 흡수 — 05 ADR V2) */
    private static final List<String> PERSON_COLUMN = List.of(
            "담당자", "담당", "작성자", "등록자", "책임자", "이름", "성명", "발견자", "요청자", "승인자",
            "연락처", "전화", "휴대", "이메일", "메일", "사번", "아이디",
            "pm", "owner", "finder", "manager", "author", "email", "phone", "tel");

    private Absorb() {}

    /** 이 컬럼의 값들이 개인정보 영역인가 — true 면 값 흡수 금지 */
    public static boolean isPersonColumn(String columnName) {
        if (columnName == null) return false;
        String s = columnName.toLowerCase(Locale.ROOT).replaceAll("[\\s()\\[\\]_-]", "");
        return PERSON_COLUMN.stream().anyMatch(s::contains);
    }

    /**
     * 흡수 제외 사유를 돌려준다. null 이면 흡수 가능.
     *
     * <p>사유 문자열은 그대로 {@code vocab_source.scope_out} 에 쌓인다 — 6개월 뒤
     * "왜 이 용어는 사전에 없지?"에 답하기 위해서다. 제외도 결정이므로 기록한다.
     */
    public static String rejectReason(String raw) {
        if (raw == null || raw.isBlank()) return "빈 값";
        String v = raw.trim();
        if (v.length() > MAX_LEN) return "문장(길이 " + v.length() + ")";
        if (v.chars().filter(Character::isWhitespace).count() > MAX_SPACES) return "문장(공백 초과)";
        if (RRN.matcher(v).matches()) return "개인정보(주민번호 형식)";
        if (PHONE.matcher(v).matches()) return "개인정보(전화번호 형식)";
        if (EMAIL.matcher(v).matches()) return "개인정보(이메일 형식)";
        if (SECRETISH.matcher(v).matches()) return "비밀·키 의심(장문 토큰)";
        if (FILE_PATH.matcher(v).matches()) return "파일명·경로";
        if (DATE.matcher(v).find()) return "날짜 값";
        if (NUMERIC.matcher(v).matches()) return "숫자 값";
        return null;
    }

    public static boolean accepts(String raw) {
        return rejectReason(raw) == null;
    }

    /** 매칭·중복제거용 정규화 — 공백·괄호·구분자 제거 후 소문자 (05 §6 ③단계) */
    public static String norm(String s) {
        if (s == null) return "";
        return s.toLowerCase(Locale.ROOT).replaceAll("[\\s()\\[\\]{}_./\\\\-]", "");
    }
}
