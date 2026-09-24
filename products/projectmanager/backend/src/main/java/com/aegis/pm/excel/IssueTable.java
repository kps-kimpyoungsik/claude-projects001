package com.aegis.pm.excel;

import java.util.regex.Pattern;

/** 이슈 시트 컬럼 규칙 — 원본 Issues.html/setIssueStatus 와 동일한 헤더 탐색 규칙 */
public final class IssueTable {

    public static final Pattern DONE_COL = Pattern.compile("완료여부|상태|진행상태");
    public static final Pattern UPDATED_COL = Pattern.compile("갱신일시|수정일시|최종수정");
    public static final String NO_COL = "순번";

    private IssueTable() {}
}
