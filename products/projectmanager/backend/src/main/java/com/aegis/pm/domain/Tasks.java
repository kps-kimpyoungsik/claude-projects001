package com.aegis.pm.domain;

import java.util.List;

/** 작업 목록 공통 규칙 — 저장소(엑셀/DB)와 무관하게 적용된다 */
public final class Tasks {

    /** 진행 대시보드에서 제외할 공정 키워드 — Apps Script DASH_EXCLUDE 이관 */
    private static final List<String> DASH_EXCLUDE = List.of("품질", "일정관리", "범위관리");

    private Tasks() {}

    /** 대시보드 표시 대상 여부 (Apps Script dashKeep_) */
    public static boolean dashKeep(Task t) {
        String s = t.path() + "|" + t.name() + "|" + t.mid() + "|" + t.small();
        return DASH_EXCLUDE.stream().noneMatch(s::contains);
    }
}
