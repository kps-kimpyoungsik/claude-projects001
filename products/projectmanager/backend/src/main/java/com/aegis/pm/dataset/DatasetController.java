package com.aegis.pm.dataset;

import java.util.List;
import java.util.Map;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 데이터셋 API — 적재된 표 자체를 다룬다.
 *
 * 업로드 창구는 POST /api/uploads 하나뿐이다(시트를 보고 Core/Dataset 으로 자동 분기).
 * 대시보드는 /api/dashboards 가 담당하고, 여기서는 "데이터셋 1개짜리 기본 대시보드"만 노출한다.
 */
@RestController
@RequestMapping("/api/datasets")
public class DatasetController {

    private final DashboardService dashboards;

    public DatasetController(DashboardService dashboards) {
        this.dashboards = dashboards;
    }

    @GetMapping
    public List<Map<String, Object>> list() {
        return dashboards.datasets();
    }

    @GetMapping("/{id}")
    public Map<String, Object> detail(@PathVariable String id) {
        return dashboards.dataset(id);
    }

    @GetMapping("/{id}/rows")
    public List<Map<String, String>> rows(@PathVariable String id,
                                          @RequestParam(defaultValue = "200") int limit) {
        return dashboards.rows(id, limit);
    }

    /** 컬럼 하나의 값 목록 — 위젯 편집에서 진척율의 완료 판정값을 고르는 데 쓴다 */
    @GetMapping("/{id}/values")
    public List<Map<String, Object>> values(@PathVariable String id,
                                            @RequestParam String col,
                                            @RequestParam(defaultValue = "30") int limit) {
        return dashboards.values(id, col, limit);
    }

    @PutMapping("/{id}/name")
    public Map<String, Object> rename(@PathVariable String id, @RequestBody Map<String, Object> body) {
        return dashboards.rename(id, String.valueOf(body.get("name")));
    }

    @DeleteMapping("/{id}")
    public Map<String, Object> delete(@PathVariable String id) {
        return dashboards.deleteDataset(id);
    }

    /** 데이터셋 기본 대시보드 (저장 구성 없으면 자동 초안) */
    @GetMapping("/{id}/dashboard")
    public Map<String, Object> dashboard(@PathVariable String id) {
        return dashboards.datasetDashboard(id);
    }

    @PutMapping("/{id}/dashboard")
    @SuppressWarnings("unchecked")
    public Map<String, Object> saveDashboard(@PathVariable String id, @RequestBody Map<String, Object> body) {
        return dashboards.saveDatasetWidgets(id, (List<Map<String, Object>>) body.get("widgets"));
    }

    @DeleteMapping("/{id}/dashboard")
    public Map<String, Object> resetDashboard(@PathVariable String id) {
        return dashboards.resetDatasetWidgets(id);
    }
}
