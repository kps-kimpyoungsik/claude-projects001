package com.aegis.pm.upload;

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
 * 엑셀 업로드 API.
 *   POST /api/uploads            xlsx 업로드 → 종류 자동 판별 후 DB 반영
 *   GET  /api/uploads            업로드 이력 (kind 필터)
 *   GET  /api/uploads/{id}/defects  그 업로드로 들어온 결함 목록
 */
@RestController
@RequestMapping("/api/uploads")
public class UploadController {

    private final UploadService service;

    public UploadController(UploadService service) {
        this.service = service;
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Map<String, Object> upload(@RequestParam("file") MultipartFile file) throws Exception {
        return service.upload(file);
    }

    @GetMapping
    public List<Map<String, Object>> batches(@RequestParam(required = false) String kind) {
        return service.batches(kind);
    }

    /** onlyNew=true(기본): 그 업로드로 "새로 추가된" 결함만 — 별도 사이트에서 늘어난 내역 */
    @GetMapping("/{batchId}/defects")
    public List<Map<String, Object>> batchDefects(@PathVariable String batchId,
                                                  @RequestParam(defaultValue = "true") boolean onlyNew) {
        return service.batchDefects(batchId, onlyNew);
    }
}
