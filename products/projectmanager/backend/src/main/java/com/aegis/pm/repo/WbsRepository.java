package com.aegis.pm.repo;

import java.util.Map;

import com.aegis.pm.domain.WbsModel;
import com.aegis.pm.excel.SheetTableReader.Table;

/**
 * WBS 데이터 저장소 포트.
 *
 * 화면·서비스는 데이터가 엑셀에서 오는지 DB에서 오는지 알지 못한다.
 * 지금은 엑셀 어댑터(ExcelWbsRepository)가 기본이고, DB로 넘어갈 때는
 * application.yml의 `wbs.source: db` 한 줄만 바꾸면 JdbcWbsRepository로 교체된다.
 */
public interface WbsRepository {

    /** 전체 WBS 모델 (필터 없음, 원본 행 순서 유지) */
    WbsModel model();

    /**
     * 헤더 기반 부속 시트 조회.
     * @param logical "issues" | "staffing"
     */
    Table table(String logical);

    /** 현재 어떤 저장소를 쓰고 있는지 — /api/meta 표시용 */
    String describe();

    /**
     * 이슈 완료여부 저장 (원본 setIssueStatus).
     * 쓰기를 지원하지 않는 저장소(엑셀)는 기본 구현이 사유를 그대로 알려준다.
     */
    default Map<String, Object> updateIssueStatus(String no, boolean done) {
        return Map.of("ok", false,
                "error", "현재 데이터 출처(" + describe() + ")는 쓰기를 지원하지 않습니다. wbs.source=db 로 전환하세요.");
    }
}
