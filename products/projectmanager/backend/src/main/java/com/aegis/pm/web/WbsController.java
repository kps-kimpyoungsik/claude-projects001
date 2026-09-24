package com.aegis.pm.web;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.aegis.pm.domain.WbsModel;
import com.aegis.pm.service.LegacyViewService;
import com.aegis.pm.service.WbsService;

/**
 * WBS 도메인 API — 경로는 전부 /api/wbs 아래에 모은다.
 *
 *   getWbsDataJson()        → GET /api/wbs
 *   (필터 없는 전체)         → GET /api/wbs/all
 *   getWeeklyProgressJson() → GET /api/wbs/weekly-progress
 *   getWeeklyArchiveJson()  → GET /api/wbs/weekly-archive
 *   getWeekSnapshotOrLive() → GET /api/wbs/week/{week}
 *
 * 이슈·투입인력·시스템 메타는 별도 컨트롤러가 담당한다(도메인 경계 분리).
 */
@RestController
@RequestMapping("/api/wbs")
public class WbsController {

    private final WbsService service;
    private final LegacyViewService legacy;

    public WbsController(WbsService service, LegacyViewService legacy) {
        this.service = service;
        this.legacy = legacy;
    }

    @GetMapping
    public WbsModel wbs() {
        return service.model();
    }

    @GetMapping("/all")
    public WbsModel wbsAll() {
        return service.modelAll();
    }

    @GetMapping("/weekly-progress")
    public Map<String, Object> weeklyProgress() {
        return service.weeklyProgress();
    }

    /** 주차별 진행 리포트 목록 (원본 getWeeklyArchiveJson) */
    @GetMapping("/weekly-archive")
    public Map<String, Object> weeklyArchive() {
        return legacy.weeklyArchive();
    }

    /** 주차 1건 (원본 getWeekSnapshotOrLive / getWeekLiveJson) */
    @GetMapping("/week/{week}")
    public Map<String, Object> weekLive(@PathVariable int week) {
        return legacy.week(week);
    }

}
