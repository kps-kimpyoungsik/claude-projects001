package com.aegis.pm.dds;

import java.util.List;
import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 정형화 성적표 (USS U5-min).
 *   GET  /api/dds/metrics               지금 값 — 전체 + 표준별
 *   POST /api/dds/metrics/snapshot      스냅샷 기록 + 직전 대비 회귀 판정
 *   GET  /api/dds/metrics/history?scope 추이
 */
@RestController
@RequestMapping("/api/dds/metrics")
public class MetricController {

    private final MetricService service;

    public MetricController(MetricService service) {
        this.service = service;
    }

    @GetMapping
    public List<Map<String, Object>> current() {
        return service.current();
    }

    @PostMapping("/snapshot")
    public Map<String, Object> snapshot() {
        return service.snapshot();
    }

    @GetMapping("/history")
    public List<Map<String, Object>> history(@RequestParam(required = false) String scope) {
        return service.history(scope);
    }
}
