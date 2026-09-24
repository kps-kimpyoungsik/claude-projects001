package com.aegis.pm.upload;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.embedded.EmbeddedDatabaseBuilder;
import org.springframework.jdbc.datasource.embedded.EmbeddedDatabaseType;

/**
 * 깨진 출처 파일명 복원 — <b>근거가 유일할 때만</b> 고치는가.
 *
 * <p>이 기능의 위험은 "못 고치는 것"이 아니라 <b>틀리게 고치는 것</b>이다. 잘못 복원하면
 * 없는 출처를 사실처럼 저장하게 되고, 그건 깨진 채로 두는 것보다 나쁘다. 그래서 테스트의
 * 무게중심이 no-evidence·ambiguous 쪽에 있다.
 */
class FilenameRepairTest {

    @TempDir Path uploads;
    @TempDir Path root;
    private JdbcTemplate jdbc;

    /** 실측된 깨짐 형태 — `_작업확인-개발WBS_결함관리_통합대장.xlsx` 가 이렇게 적재됐다 */
    private static final String BROKEN =
            "_���-��WBS_����_����.xlsx";
    private static final String GOOD = "_작업확인-개발WBS_결함관리_통합대장.xlsx";

    @BeforeEach
    void setUp() {
        jdbc = new JdbcTemplate(new EmbeddedDatabaseBuilder()
                .setType(EmbeddedDatabaseType.H2).generateUniqueName(true).build());
        jdbc.execute("CREATE TABLE dataset (dataset_id VARCHAR(60) PRIMARY KEY, source_file VARCHAR(300))");
        jdbc.execute("CREATE TABLE upload_batch (batch_id VARCHAR(40) PRIMARY KEY, file_name VARCHAR(300))");
    }

    private FilenameRepair repair() {
        return new FilenameRepair(jdbc, uploads, root);
    }

    private void touch(Path dir, String name) throws Exception {
        Files.write(dir.resolve(name), new byte[] { 'P', 'K', 3, 4 });
    }

    private void seedBroken(int datasets) {
        for (int i = 1; i <= datasets; i++) {
            jdbc.update("INSERT INTO dataset VALUES (?,?)", "DS-" + i, BROKEN);
        }
        jdbc.update("INSERT INTO upload_batch VALUES (?,?)", "UP-1", BROKEN);
    }

    // ── 골격 대조 ──────────────────────────────────────────────────────────

    @Test
    void 깨져도_ASCII_골격은_남는다() {
        assertEquals(FilenameRepair.skeleton(GOOD), FilenameRepair.skeleton(BROKEN),
                "복원이 성립하는 유일한 근거다 — 이게 깨지면 이 기능 전체가 성립하지 않는다");
        assertEquals("_#-#WBS_#_#.xlsx", FilenameRepair.skeleton(BROKEN));
    }

    @Test
    void 정상_이름은_깨진_것으로_보지_않는다() {
        assertFalse(FilenameRepair.broken(GOOD));
        assertTrue(FilenameRepair.broken(BROKEN));
    }

    // ── 유일 근거일 때만 복원 ──────────────────────────────────────────────

    @Test
    void 후보가_하나면_복원한다_그리고_관계가_유지된다() throws Exception {
        seedBroken(10);                       // 한 파일이 데이터셋 10개를 만든 실측 상황
        touch(root, GOOD);
        touch(root, "무관한파일.xlsx");

        Map<String, Object> dry = repair().repair(false);
        assertEquals(1, dry.get("repairable"));
        assertEquals("repairable", item(dry).get("verdict"));
        assertEquals(10L, jdbc.queryForObject(
                "SELECT count(*) FROM dataset WHERE source_file = ?", Long.class, BROKEN),
                "dry 는 한 줄도 바꾸지 않는다");

        Map<String, Object> applied = repair().repair(true);
        assertEquals(10, applied.get("datasetRowsUpdated"));
        assertEquals(1, applied.get("uploadBatchRowsUpdated"));
        assertEquals(10L, jdbc.queryForObject(
                "SELECT count(*) FROM dataset WHERE source_file = ?", Long.class, GOOD),
                "10개가 같은 값으로 복원돼야 '같은 출처' 그룹이 살아난다 — 이게 복원의 목적이다");
    }

    @Test
    void 업로드_보관본의_배치접두사는_벗겨내고_대조한다() throws Exception {
        seedBroken(1);
        touch(uploads, "UP-20260919-170632_" + GOOD);   // 보관본은 접두사가 붙어 있다
        assertEquals(1, repair().repair(false).get("repairable"));
    }

    // ── 근거가 부족하면 건드리지 않는다 (이쪽이 더 중요하다) ────────────────

    @Test
    void 후보가_없으면_고치지_않고_보고만_한다() {
        seedBroken(3);
        Map<String, Object> r = repair().repair(true);
        assertEquals(0, r.get("repairable"));
        assertEquals("no-evidence", item(r).get("verdict"));
        assertEquals(3L, jdbc.queryForObject(
                "SELECT count(*) FROM dataset WHERE source_file = ?", Long.class, BROKEN),
                "근거가 없으면 깨진 채로 두는 것이 옳다 — 지어내지 않는다");
    }

    @Test
    void 후보가_둘이면_구분_불가로_두고_고치지_않는다() throws Exception {
        seedBroken(1);
        touch(root, GOOD);
        touch(root, "_가나다-라마WBS_바사아자_차카타파.xlsx");   // 골격이 같은 다른 파일

        Map<String, Object> r = repair().repair(true);
        assertEquals(0, r.get("repairable"));
        assertEquals("ambiguous", item(r).get("verdict"));
        assertEquals(2, ((List<?>) item(r).get("matches")).size());
        assertEquals(1L, jdbc.queryForObject(
                "SELECT count(*) FROM dataset WHERE source_file = ?", Long.class, BROKEN),
                "둘 중 하나를 고르는 것은 추측이다 — 사람이 판단해야 한다");
    }

    @Test
    void 깨진_이름_자신은_후보가_되지_않는다() throws Exception {
        seedBroken(1);
        touch(uploads, "UP-20260919-170632_" + BROKEN);   // 보관본 이름도 깨져 있는 실제 상황
        Map<String, Object> r = repair().repair(true);
        assertEquals("no-evidence", item(r).get("verdict"),
                "깨진 것으로 깨진 것을 고치면 아무것도 나아지지 않는다");
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> item(Map<String, Object> result) {
        return ((List<Map<String, Object>>) result.get("items")).get(0);
    }
}
