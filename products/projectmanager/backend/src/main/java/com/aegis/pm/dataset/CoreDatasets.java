package com.aegis.pm.dataset;

import java.util.Map;

/**
 * Core 영역이 쓰는 고정 데이터셋 ID.
 *
 * WBS 엑셀의 부속 시트(이슈·투입인력)는 도메인 계산이 없는 "그냥 표"라서 전용 테이블을 두지 않고
 * 범용 dataset 모델에 담는다. ID를 고정해 두면 Core 화면이 항상 같은 자리에서 읽을 수 있고,
 * 동시에 '데이터셋' 화면에서도 그대로 보인다 — 저장 모델이 하나라서 가능한 일이다.
 */
public final class CoreDatasets {

    public static final String ISSUES = "DS-CORE-issues";
    public static final String STAFFING = "DS-CORE-staffing";

    private static final Map<String, String> BY_LOGICAL = Map.of(
            "issues", ISSUES,
            "staffing", STAFFING);

    private CoreDatasets() {}

    /** WbsRepository.table(logical) 의 논리명 → 고정 데이터셋 ID */
    public static String of(String logical) {
        return BY_LOGICAL.get(logical);
    }
}
