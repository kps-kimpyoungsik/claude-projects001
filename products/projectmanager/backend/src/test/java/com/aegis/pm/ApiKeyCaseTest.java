package com.aegis.pm;

import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import com.aegis.pm.unittest.DefectService;
import com.aegis.pm.upload.UploadService;

/**
 * API 응답 키는 <b>소문자</b>다 — 화면이 그 이름으로 읽는다.
 *
 * <p>H2 는 `SELECT *` 결과 키를 대문자로, PostgreSQL 은 소문자로 준다. 대문자를 그대로
 * 내보내면 화면의 `r.defect_id` 가 전부 undefined 가 되는데, <b>오류가 아니라 빈 값</b>이라
 * 아무도 틀린 줄 모른다. 실측에서 `/api/defects` 와 `/api/uploads` 가 그 상태였다.
 *
 * <p>이 결함을 네 번 겪었다(dds 3회 + Core 1회). 그래서 문구가 아니라 <b>테스트로</b> 못박는다.
 */
@SpringBootTest(properties = {
        "wbs.source=excel",
        "wbs.import-on-start=false",
        "spring.datasource.url=jdbc:h2:mem:apikeycase;DB_CLOSE_DELAY=-1",
        "spring.sql.init.mode=always"
})
class ApiKeyCaseTest {

    @Autowired DefectService defects;
    @Autowired UploadService uploads;
    @Autowired JdbcTemplate jdbc;

    @BeforeEach
    void seed() {
        jdbc.update("DELETE FROM defect");
        jdbc.update("""
                INSERT INTO defect (defect_id, reg_dt, status, content, source)
                VALUES ('DF-2026-001','2026-07-01','신규','테스트','manual')
                """);
        jdbc.update("DELETE FROM upload_batch");
        jdbc.update("""
                INSERT INTO upload_batch (batch_id, kind, file_name, uploaded_at)
                VALUES ('UP-20260101-000000-a','defect','t.xlsx','2026-01-01 00:00:00')
                """);
    }

    @Test
    void 결함_목록_키가_소문자다() {
        assertLower(defects.list(null, null, null, null), "Defects.jsx 는 r.defect_id 로 읽는다");
    }

    @Test
    void 업로드_이력_키가_소문자다() {
        assertLower(uploads.batches(null), "Defects.jsx 는 x.batch_id 로 읽는다");
    }

    /** 키에 대문자 알파벳이 섞이면 실패 — 이름을 그대로 찍어 어디가 틀렸는지 바로 보이게 한다 */
    private static void assertLower(List<Map<String, Object>> rows, String why) {
        assertTrue(!rows.isEmpty(), "표본이 없으면 검증이 성립하지 않는다");
        List<String> upper = rows.get(0).keySet().stream()
                .filter(k -> k.chars().anyMatch(Character::isUpperCase))
                .toList();
        assertTrue(upper.isEmpty(),
                "대문자 키가 남아 있다: " + upper + " — " + why
                + " (오류가 아니라 undefined 로 조용히 깨진다)");
    }
}
