package com.aegis.pm.unittest;

import java.util.List;
import java.util.Map;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 단위테스트 영역 API.
 *
 *   IA 개발완료 범위 (원본 IaScope.html 이 그대로 사용)
 *     getIaScopeJson()   → GET  /api/ia/scope
 *     setIaStatus()      → POST /api/ia/status
 *     getDefectDashJson()→ GET  /api/defects/dash
 *
 *   결함 관리 (신규 CRUD)
 *     GET    /api/defects            목록(status·q 필터)
 *     POST   /api/defects            등록
 *     PUT    /api/defects/{id}       수정
 *     DELETE /api/defects/{id}       삭제
 *     POST   /api/defects/sync       IA 기획 피드백 이벤트 → 결함 자동 등록
 *     POST   /api/unittest/import    참고 시트만 DB 적재
 */
@RestController
@RequestMapping("/api")
public class UnitTestController {

    private final IaScopeService ia;
    private final DefectService defects;
    private final IaImportService importer;

    public UnitTestController(IaScopeService ia, DefectService defects, IaImportService importer) {
        this.ia = ia;
        this.defects = defects;
        this.importer = importer;
    }

    @GetMapping("/ia/scope")
    public Map<String, Object> scope() {
        return ia.scope();
    }

    @PostMapping("/ia/status")
    public Map<String, Object> setStatus(@RequestBody Map<String, Object> body) {
        return ia.setStatus(body);
    }

    @GetMapping("/defects")
    public List<Map<String, Object>> defects(@RequestParam(required = false) String status,
                                             @RequestParam(required = false) String q,
                                             @RequestParam(required = false) String source,
                                             @RequestParam(required = false) String batchId) {
        return defects.list(status, q, source, batchId);
    }

    @GetMapping("/defects/dash")
    public Map<String, Object> defectDash() {
        return defects.dashboard();
    }

    @GetMapping("/defects/statuses")
    public List<String> defectStatuses() {
        return defects.statuses();
    }

    @PostMapping("/defects")
    public Map<String, Object> createDefect(@RequestBody Map<String, Object> body) {
        return defects.create(body);
    }

    @PutMapping("/defects/{id}")
    public Map<String, Object> updateDefect(@PathVariable String id, @RequestBody Map<String, Object> body) {
        return defects.update(id, body);
    }

    @DeleteMapping("/defects/{id}")
    public Map<String, Object> deleteDefect(@PathVariable String id) {
        return defects.delete(id);
    }

    /** IA 기획 피드백 → 결함 자동 등록 (dry=1 이면 대상만 확인) */
    @PostMapping("/defects/sync")
    public Map<String, Object> syncDefects(@RequestParam(defaultValue = "false") boolean dry) {
        return defects.syncFromIa(dry);
    }

    @PostMapping("/unittest/import")
    public Map<String, Object> importUnitTest() {
        return importer.importAll();
    }
}
