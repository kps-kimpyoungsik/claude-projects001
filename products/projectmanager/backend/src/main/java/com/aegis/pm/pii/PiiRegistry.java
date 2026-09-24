package com.aegis.pm.pii;

import java.util.List;
import java.util.regex.Pattern;

/**
 * 개인정보 분류의 <b>유일한 정본</b> (지침 G-1). 새 개인정보 컬럼·업로드 형식은 여기에 먼저 적는다.
 *
 * <p>등급: P0 공개 · P1 가명 · P2 개인정보(토큰+금고) · P3 민감·고유식별(적재 금지). 설계서 §5.
 */
public final class PiiRegistry {

    private PiiRegistry() {}

    public static final String PERSON = "person_name";
    public static final String PHONE = "phone";
    public static final String EMAIL = "email";

    /** 업무 테이블의 P2 컬럼 — 적재 시 토큰, 전환 API 가 기존 평문을 토큰으로 바꾼다 */
    public record Column(String table, String column, String kind) {}

    public static final List<Column> COLUMNS = List.of(
            new Column("wbs_task", "owner", PERSON),
            new Column("ia_screen", "owner", PERSON),
            new Column("defect", "owner", PERSON),
            new Column("defect", "finder", PERSON));

    /**
     * 자유 텍스트 컬럼 — 이름이 섞여 들어온다(실측: 결함 내용·조치·IA 비고·WBS 작업명에 10명).
     * 금고에 있는 사람만 토큰으로 바꾼다(PiiVault.scrub). 칸 전체를 암호화하지 않는 이유: 검색·표시가 깨진다.
     */
    public static final List<Column> TEXT_COLUMNS = List.of(
            new Column("defect", "content", PERSON), new Column("defect", "repro", PERSON),
            new Column("defect", "action", PERSON), new Column("defect", "remark", PERSON),
            new Column("ia_screen", "note", PERSON), new Column("ia_screen", "remark", PERSON),
            new Column("ia_screen", "plan_note", PERSON),
            new Column("wbs_task", "name", PERSON), new Column("wbs_task", "path", PERSON),
            new Column("wbs_task", "big", PERSON), new Column("wbs_task", "mid", PERSON),
            new Column("wbs_task", "small", PERSON), new Column("wbs_task", "note", PERSON));

    /** 업로드 시트 헤더 → P2 종류. 이름이 곧 분류 근거라 오탐보다 누락이 더 위험하다 — 넓게 잡는다 */
    private static final List<Object[]> HEADERS = List.of(
            new Object[] { Pattern.compile("담당|성명|이름|작성자|발견자|요청자|검토자|승인자|책임자|수행자|개발자|PM\\b|name|owner|assignee|author", Pattern.CASE_INSENSITIVE), PERSON },
            new Object[] { Pattern.compile("연락처|전화|휴대|핸드폰|phone|mobile|tel", Pattern.CASE_INSENSITIVE), PHONE },
            new Object[] { Pattern.compile("메일|e-?mail", Pattern.CASE_INSENSITIVE), EMAIL });

    /**
     * 담당자 칸에 들어오는 <b>사람이 아닌</b> 값 — 역할·조직·미정 표기 (실측 2026-09-24: 기획 99건·미정·전체·고객사·
     * "자금운영,홍길동"·"홍길동,모바일팀" 같은 복합값). 이런 조각은 평문(P0)으로 둔다.
     */
    private static final Pattern ROLE = Pattern.compile(
            "(팀|사|부서|센터|그룹|파트|업체|현업|기획|개발|디자인|퍼블|운영|공통|미정|미지정|전체|테스트|전산|담당|협력|발주)$"
                    + "|^(QA|PM|PL|TA|AA|DBA|N/?A|-)$", Pattern.CASE_INSENSITIVE);
    private static final Pattern HANGUL_NAME = Pattern.compile("[가-힣]{2,4}");

    public static boolean isRole(String part) {
        return ROLE.matcher(part.trim()).find();
    }

    /** 사람 이름으로 보이는 조각 — 한글 2~4자이고 역할어가 아님 */
    public static boolean isPersonLike(String part) {
        return HANGUL_NAME.matcher(part).matches() && !isRole(part);
    }

    /** 이름으로 보이지만 개인정보가 아닌 헤더 — 화면명·시스템명·파일명 등 */
    private static final Pattern NOT_PERSON = Pattern.compile("화면|시스템|파일|업무|메뉴|프로그램|항목|필드|컬럼|시트|프로젝트|과제|테이블|기능");

    /** @return P2 종류, 개인정보 헤더가 아니면 null */
    public static String kindOfHeader(String header) {
        // 컬럼명이 아닌 것 — 실측: HTML 가이드 시트의 "헤더"가 <li ... name="..."> 조각이라 성명으로 오분류됐다
        if (header == null || header.length() > 40 || header.indexOf('<') >= 0) return null;
        for (Object[] h : HEADERS) {
            if (((Pattern) h[0]).matcher(header).find()) {
                if (PERSON.equals(h[1]) && NOT_PERSON.matcher(header).find()) return null;
                return (String) h[1];
            }
        }
        return null;
    }

    /**
     * P3 — 적재 금지(지침 G-3). 주민·외국인등록번호(생년월일 6 + 성별 1 + 6), 여권, 카드번호.
     * 셀 값 자체를 보고 판정한다 — 헤더를 믿으면 "비고" 칸에 적힌 주민번호를 놓친다.
     */
    private static final Pattern P3 = Pattern.compile(
            "\\b\\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\\d|3[01])-?[1-8]\\d{6}\\b"   // 주민·외국인등록번호
                    + "|\\b[MSRODG]\\d{8}\\b"                                   // 여권
                    + "|\\b\\d{4}-\\d{4}-\\d{4}-\\d{4}\\b");                    // 카드

    public static boolean isP3(String value) {
        return value != null && P3.matcher(value).find();
    }
}
