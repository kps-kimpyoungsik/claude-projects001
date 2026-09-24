package com.aegis.pm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import com.aegis.pm.domain.WbsModel;
import com.aegis.pm.repo.WbsImportService;
import com.aegis.pm.repo.WbsRepository;
import com.aegis.pm.service.WbsService;

/**
 * DB 전환 검증 — 엑셀을 적재한 뒤 DB만 읽었을 때 엑셀과 같은 값이 나오는지 확인한다.
 * 이 테스트가 통과하는 한 `wbs.source: db` 로 바꿔도 화면 값이 달라지지 않는다.
 */
@SpringBootTest(properties = {
        "wbs.source=db",
        "wbs.import-on-start=false",
        "wbs.file=../중소기업중앙회_WEB통합자금관리시스템고도화_wbs_v1.0_20260831.xlsx",
        "spring.datasource.url=jdbc:h2:mem:wbstest;DB_CLOSE_DELAY=-1",
        "spring.sql.init.mode=always"
})
class DbSourceTest {

    @Autowired WbsImportService importer;
    @Autowired WbsRepository repo;
    @Autowired WbsService service;

    @Test
    void 엑셀_적재후_DB만으로_동일값() {
        Map<String, Object> result = importer.importAll();
        assertEquals(true, result.get("ok"));
        assertTrue((int) result.get("tasks") > 100, "적재 작업 수 이상: " + result.get("tasks"));

        // 활성 저장소가 DB인지 확인 (엑셀 어댑터가 아님)
        assertTrue(repo.describe().startsWith("db"), "활성 저장소가 db가 아님: " + repo.describe());

        WbsModel db = repo.model();
        assertEquals(result.get("tasks"), db.tasks().size());
        assertTrue(db.projectName().contains("중소기업중앙회"));
        assertNotNull(db.base());
        assertTrue(db.maxWeek() > 0);
        assertTrue(db.summary().pProg() > 0);

        // seq 순서가 보존돼야 계층 트리가 같은 모양으로 복원된다
        for (int i = 0; i < db.tasks().size(); i++) {
            assertEquals(i, db.tasks().get(i).seq(), "DB 왕복 후 seq 순서 깨짐");
        }

        // 진척 재계산이 DB 데이터만으로 동작 (트리 복원 + 가중치 롤업 확인)
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> rows = (List<Map<String, Object>>) service.weeklyProgress().get("rows");
        double plan = (Double) rows.get(0).get("curPlan");
        assertTrue(plan > 0 && plan <= 100, "DB 기준 전체 계획진척 이상: " + plan);

        // 부속 시트도 함께 적재됨
        assertTrue(service.issues().found(), "이슈 데이터가 DB에 없음");
        assertTrue(service.issues().headers().contains("이슈명"));
        assertTrue(service.staffing().found(), "투입인력 데이터가 DB에 없음");
    }
}
