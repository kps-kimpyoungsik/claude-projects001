package com.aegis.pm.web;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.aegis.pm.excel.SheetTableReader;
import com.aegis.pm.service.WbsService;

/** 시스템 공통 API — 데이터 출처 확인, 도메인에 속하지 않는 부속 표 */
@RestController
@RequestMapping("/api")
public class SystemController {

    private final WbsService service;

    public SystemController(WbsService service) {
        this.service = service;
    }

    /** 현재 데이터 출처(excel/db)·프로젝트명·기준일 */
    @GetMapping("/meta")
    public Map<String, Object> meta() {
        return service.meta();
    }

    /** 투입인력현황 — 계산 로직이 없는 표라 데이터셋에 적재돼 있다 */
    @GetMapping("/staffing")
    public SheetTableReader.Table staffing() {
        return service.staffing();
    }
}
