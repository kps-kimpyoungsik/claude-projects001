package com.aegis.pm.web;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.aegis.pm.service.WbsService;

/** 이슈 도메인 API — WBS 엑셀의 '이슈페이지' 시트가 원천이며 DB(데이터셋)에 적재돼 있다 */
@RestController
@RequestMapping("/api/issues")
public class IssueController {

    private final WbsService service;

    public IssueController(WbsService service) {
        this.service = service;
    }

    @GetMapping
    public Map<String, Object> issues() {
        return service.issuesJson();
    }

    /** 완료여부 저장 (원본 setIssueStatus) */
    @PostMapping("/status")
    public Map<String, Object> setStatus(@RequestBody Map<String, Object> body) {
        return service.setIssueStatus(String.valueOf(body.get("no")), Boolean.TRUE.equals(body.get("done")));
    }
}
