package com.aegis.pm.dataset;

import java.util.List;
import java.util.Map;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 대시보드 API — **메뉴 정의가 DB에 있다.**
 *
 *   GET    /api/dashboards          대시보드 목록
 *   GET    /api/dashboards/menu     LNB 가 읽는 메뉴 (show_in_menu = true)
 *   POST   /api/dashboards          새 대시보드
 *   GET    /api/dashboards/{id}     위젯 렌더 결과 (여러 데이터셋 혼합 가능)
 *   PUT    /api/dashboards/{id}     이름·설명·메뉴노출 변경
 *   PUT    /api/dashboards/{id}/widgets  위젯 구성 저장
 *   DELETE /api/dashboards/{id}     삭제
 */
@RestController
@RequestMapping("/api/dashboards")
public class DashboardController {

    private final DashboardService service;

    public DashboardController(DashboardService service) {
        this.service = service;
    }

    @GetMapping
    public List<Map<String, Object>> list() {
        return service.dashboards();
    }

    @GetMapping("/menu")
    public List<Map<String, Object>> menu() {
        return service.menu();
    }

    @PostMapping
    public Map<String, Object> create(@RequestBody Map<String, Object> body) {
        return service.createDashboard(
                String.valueOf(body.getOrDefault("name", "새 대시보드")),
                String.valueOf(body.getOrDefault("description", "")));
    }

    /** 저장하지 않고 계산만 — 편집 중 미리보기 (구성을 바꿀 때마다 DB 를 쓰지 않는다) */
    @PostMapping("/preview")
    @SuppressWarnings("unchecked")
    public Map<String, Object> preview(@RequestBody Map<String, Object> body) {
        return service.preview((List<Map<String, Object>>) body.get("widgets"));
    }

    @GetMapping("/{id}")
    public Map<String, Object> detail(@PathVariable String id) {
        return service.customDashboard(id);
    }

    @PutMapping("/{id}")
    public Map<String, Object> update(@PathVariable String id, @RequestBody Map<String, Object> body) {
        return service.updateDashboard(id, body);
    }

    @PutMapping("/{id}/widgets")
    @SuppressWarnings("unchecked")
    public Map<String, Object> saveWidgets(@PathVariable String id, @RequestBody Map<String, Object> body) {
        return service.saveWidgets(id, (List<Map<String, Object>>) body.get("widgets"));
    }

    @DeleteMapping("/{id}")
    public Map<String, Object> delete(@PathVariable String id) {
        return service.deleteDashboard(id);
    }
}
