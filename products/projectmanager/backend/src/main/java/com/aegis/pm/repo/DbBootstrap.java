package com.aegis.pm.repo;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

import com.aegis.pm.config.WbsProperties;
import com.aegis.pm.unittest.IaImportService;

/**
 * DB가 비어 있으면 기동 시 엑셀을 한 번 적재한다 (최초 1회 — 이후 갱신은 명시 호출).
 *   WBS      : source=db 일 때만 (source=excel 이면 조회가 엑셀 직독이라 적재가 필요 없다)
 *   IA·결함  : source 와 무관하게 항상 (이 둘은 언제나 DB 기준으로 동작한다)
 */
@Configuration
public class DbBootstrap {

    private static final Logger log = LoggerFactory.getLogger(DbBootstrap.class);

    @Bean
    ApplicationRunner importIfEmpty(JdbcTemplate jdbc, WbsImportService importer,
                                    IaImportService iaImporter, WbsProperties props) {
        return args -> {
            if (!props.isImportOnStart()) {
                log.info("[DB] import-on-start=false — 자동 적재 생략");
                return;
            }
            if ("db".equalsIgnoreCase(props.getSource())) {
                Integer n = jdbc.queryForObject("SELECT COUNT(*) FROM wbs_task", Integer.class);
                if (n == null || n == 0) {
                    log.info("[DB] WBS 비어 있음 — 엑셀 자동 적재 시작: {}", importer.sourceDescription());
                    log.info("[DB] WBS 자동 적재 완료: {}", importer.importAll());
                } else {
                    log.info("[DB] WBS 기존 적재 {}건 — 생략 (갱신은 POST /api/admin/import)", n);
                }
            }

            Integer m = jdbc.queryForObject("SELECT COUNT(*) FROM ia_screen", Integer.class);
            if (m == null || m == 0) {
                log.info("[DB] IA 비어 있음 — 자동 적재: {}건", iaImporter.importIa());
            } else {
                log.info("[DB] IA 기존 적재 {}건 — 생략 (갱신은 POST /api/unittest/import)", m);
            }

            Integer d = jdbc.queryForObject("SELECT COUNT(*) FROM defect", Integer.class);
            if (d == null || d == 0) {
                log.info("[DB] 결함 비어 있음 — 자동 적재: {}건", iaImporter.importDefects());
            } else {
                log.info("[DB] 결함 기존 적재 {}건 — 생략", d);
            }
        };
    }
}
