package com.aegis.pm.engine;

import java.util.List;
import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 범용 규칙 발견 엔진 API.
 *
 * <pre>
 *   GET  /api/engine/inventory        자료 리스트업 — 전 데이터셋 구조·역할·헤더 의심·정제 제안 요약
 *   GET  /api/engine/profile/{id}     컬럼별 특징·역할·근거 + 정제 계획
 *   POST /api/engine/refine/{id}      정제 적용 — 원본은 두고 {id}-R 새 데이터셋
 * </pre>
 */
@RestController
@RequestMapping("/api/engine")
public class EngineController {

    private final EngineService engine;

    public EngineController(EngineService engine) {
        this.engine = engine;
    }

    @GetMapping("/inventory")
    public List<Map<String, Object>> inventory() {
        return engine.inventory();
    }

    @GetMapping("/profile/{id}")
    public Map<String, Object> profile(@PathVariable String id) {
        return engine.profile(id);
    }

    @PostMapping("/refine/{id}")
    public Map<String, Object> refine(@PathVariable String id) {
        return engine.apply(id);
    }
}
