package com.aegis.pm.dds;

import java.util.List;
import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * DDS 패싯(Phase 3) · 자격 게이트(Phase 4) API.
 *
 * <pre>
 *   GET  /api/dds/facets/{id}                     패싯 (분야·컬럼 의미·맥락)
 *   PUT  /api/dds/facets/{id}                     사람 지정 {axis, col?, value} — 재분류가 덮지 않는다
 *   GET  /api/dds/qualification                   전체 판정 (점수 낮은 순)
 *   GET  /api/dds/qualification/{id}              1건 — 8요소 점수 내역
 *   POST /api/dds/qualify?id=                     평가 (id 없으면 전체) — 패싯을 먼저 다시 매긴다
 *   POST /api/dds/qualification/{id}/override     사람 판정 {verdict, by}
 *   POST /api/dds/qualification/{id}/release      사람 판정 해제 → 자동 판정
 *   POST /api/dds/pipeline/{id}                   바인딩 → 패싯 → 판정을 지금 다시
 * </pre>
 */
@RestController
@RequestMapping("/api/dds")
public class QualityController {

    private final FacetService facets;
    private final QualificationService qualification;
    private final DatasetPipeline pipeline;
    private final org.springframework.jdbc.core.JdbcTemplate jdbc;

    public QualityController(FacetService facets, QualificationService qualification, DatasetPipeline pipeline,
                             org.springframework.jdbc.core.JdbcTemplate jdbc) {
        this.facets = facets;
        this.qualification = qualification;
        this.pipeline = pipeline;
        this.jdbc = jdbc;
    }

    @GetMapping("/facets/{id}")
    public List<Map<String, Object>> facets(@PathVariable String id) {
        return facets.facets(id);
    }

    @PutMapping("/facets/{id}")
    public Map<String, Object> setFacet(@PathVariable String id, @RequestBody Map<String, String> body) {
        return facets.setHuman(id, body.get("axis"), body.get("col"), body.get("value"));
    }

    @GetMapping("/qualification")
    public List<Map<String, Object>> qualifications() {
        return qualification.list();
    }

    @GetMapping("/qualification/{id}")
    public Map<String, Object> qualificationOf(@PathVariable String id) {
        Map<String, Object> q = qualification.current(id);
        if (q == null) throw new IllegalArgumentException("아직 평가하지 않았습니다: " + id);
        return q;
    }

    @PostMapping("/qualify")
    public Map<String, Object> qualify(@RequestParam(required = false) String id) {
        if (id != null && !id.isBlank()) {
            facets.classify(id);
            return qualification.evaluate(id);
        }
        for (String ds : jdbc.queryForList("SELECT dataset_id FROM dataset", String.class)) facets.classify(ds);
        return qualification.evaluateAll();
    }

    @PostMapping("/qualification/{id}/override")
    public Map<String, Object> override(@PathVariable String id, @RequestBody Map<String, String> body) {
        return qualification.override(id, body.get("verdict"), body.get("by"));
    }

    @PostMapping("/qualification/{id}/release")
    public Map<String, Object> release(@PathVariable String id) {
        return qualification.release(id);
    }

    @PostMapping("/pipeline/{id}")
    public Map<String, Object> rerun(@PathVariable String id) {
        return pipeline.run(id);
    }
}
