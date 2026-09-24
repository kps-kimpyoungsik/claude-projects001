package com.aegis.pm.pii;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** 개인정보 보호 상태·전환. POST 는 ApiKeyFilter 가 쓰기 API 키를 요구한다 */
@RestController
@RequestMapping("/api/admin/pii")
public class PiiController {

    private final PiiMigrationService migration;

    public PiiController(PiiMigrationService migration) {
        this.migration = migration;
    }

    @GetMapping("/status")
    public Map<String, Object> status() {
        return migration.status();
    }

    @PostMapping("/migrate")
    public Map<String, Object> migrate() {
        return migration.migrate();
    }
}
