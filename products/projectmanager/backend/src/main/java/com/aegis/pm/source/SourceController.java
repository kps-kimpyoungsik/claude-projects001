package com.aegis.pm.source;

import java.util.List;
import java.util.Map;

import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

/**
 * 비정형 자료 API (USS L2).
 *   POST /api/sources                   아무 파일 → 원본 보관 + 조각·좌표 (같은 원본은 재사용)
 *   GET  /api/sources                   원본 문서 목록
 *   GET  /api/sources/{docId}/fragments 조각 목록 ?limit=500(최대 5000) — locator 로 원본 위치를 되짚는다
 */
@RestController
@RequestMapping("/api/sources")
public class SourceController {

    private final SourceService service;

    public SourceController(SourceService service) {
        this.service = service;
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Map<String, Object> ingest(@RequestParam("file") MultipartFile file) throws Exception {
        return service.ingest(file);
    }

    @GetMapping
    public List<Map<String, Object>> docs() {
        return service.docs();
    }

    @GetMapping("/{docId}/fragments")
    public List<Map<String, Object>> fragments(@PathVariable String docId,
                                               @RequestParam(defaultValue = "500") int limit) {
        return service.fragments(docId, limit);
    }
}
