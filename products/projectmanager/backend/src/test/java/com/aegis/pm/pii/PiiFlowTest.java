package com.aegis.pm.pii;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyPair;
import java.util.Base64;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.aegis.pm.dataset.DatasetWriter;
import com.aegis.pm.unittest.DefectService;

/**
 * 적재 → 저장 → 응답 전 구간 (pii 설계서 §6·§7). 통과 기준:
 * 업무 테이블·payload·컬럼 프로파일에 원문 0건 · 응답에 토큰 0건(마스킹) · 수정 폼 되돌림 · 검색 · 전환 멱등.
 */
@SpringBootTest(properties = {
        "wbs.source=excel",
        "wbs.import-on-start=false",
        "spring.datasource.url=jdbc:h2:mem:piiflow;DB_CLOSE_DELAY=-1",
        "spring.sql.init.mode=always"
})
class PiiFlowTest {

    static final KeyPair KP;
    static final Path DIR;
    static {
        try {
            KP = PiiCrypto.generate();
            DIR = Files.createTempDirectory("pii-test");
            Files.writeString(DIR.resolve("pub.pem"), "-----BEGIN PUBLIC KEY-----\n"
                    + Base64.getMimeEncoder().encodeToString(KP.getPublic().getEncoded()) + "\n-----END PUBLIC KEY-----\n");
            Files.writeString(DIR.resolve("priv.pem"), "-----BEGIN PRIVATE KEY-----\n"
                    + Base64.getMimeEncoder().encodeToString(KP.getPrivate().getEncoded()) + "\n-----END PRIVATE KEY-----\n");
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    @DynamicPropertySource
    static void keys(DynamicPropertyRegistry r) {
        r.add("pm.pii.public-key", () -> "file:" + DIR.resolve("pub.pem"));
        r.add("pm.pii.private-key", () -> DIR.resolve("priv.pem").toString());
        r.add("pm.pii.index-key", PiiCrypto::newIndexKey);
        r.add("pm.pii.reveal", () -> "false");
        // 전환이 원본을 봉인·이동한다 — 실제 data/ 를 절대 건드리지 않게 임시 폴더로 (WRG-007, 2026-09-24 사고)
        r.add("pm.pii.uploads-dir", () -> DIR.resolve("uploads").toString());
        r.add("pm.pii.sources-dir", () -> DIR.resolve("sources").toString());
        r.add("pm.pii.hold-dir", () -> DIR.resolve("hold").toString());
    }

    @Autowired DefectService defects;
    @Autowired DatasetWriter datasets;
    @Autowired PiiMigrationService migration;
    @Autowired PiiVault vault;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper http;   // HTTP 응답과 같은 매퍼

    /**
     * 안전 검사 — 이 테스트 전후로 실제 data/uploads · data/_backup 의 파일 목록·크기가 같아야 한다
     * (2026-09-24 사고 재발 방지). ".sealed 가 있으면 실패" 로 두면 운영 전환 뒤 정상 봉인 파일에 오탐한다(실측).
     */
    private static String realSnapshot;

    private static String snapshot() throws Exception {
        StringBuilder sb = new StringBuilder();
        for (Path dir : List.of(java.nio.file.Paths.get("data", "uploads"), java.nio.file.Paths.get("data", "_backup"))) {
            if (!Files.isDirectory(dir)) { sb.append(dir).append(":none;"); continue; }
            try (var w = Files.walk(dir)) {
                for (Path p : w.sorted().toList()) sb.append(p).append('=').append(Files.isRegularFile(p) ? Files.size(p) : -1).append(';');
            }
        }
        return sb.toString();
    }

    @org.junit.jupiter.api.BeforeAll
    static void realDataBefore() throws Exception {
        realSnapshot = snapshot();
    }

    @org.junit.jupiter.api.AfterAll
    static void realDataUntouched() throws Exception {
        assertEquals(realSnapshot, snapshot(), "테스트가 실제 data/uploads · data/_backup 을 바꿨다");
    }

    @BeforeEach
    void reset() throws Exception {
        for (String d : List.of("uploads", "hold")) {       // 테스트마다 빈 폴더
            Path p = DIR.resolve(d);
            if (Files.exists(p)) try (var w = Files.walk(p)) {
                w.sorted(java.util.Comparator.reverseOrder()).forEach(x -> x.toFile().delete());
            }
        }
        for (String t : List.of("defect", "wbs_task", "dataset_row", "dataset_column", "dataset", "pii_vault")) {
            jdbc.update("DELETE FROM " + t);
        }
    }

    private String ownerInDb(String id) {
        return jdbc.queryForObject("SELECT owner FROM defect WHERE defect_id = ?", String.class, id);
    }

    @Test
    void 결함_담당자는_토큰으로_저장되고_원문은_금고에_암호문으로만_있다() {
        defects.create(Map.of("defectId", "D-1", "content", "로그인 오류", "owner", "홍길동", "finder", "김철수"));

        String t = ownerInDb("D-1");
        assertTrue(PiiCrypto.isToken(t), "업무 테이블에 원문이 있으면 안 된다: " + t);
        String enc = jdbc.queryForObject("SELECT enc FROM pii_vault WHERE token = ?", String.class, t);
        assertFalse(enc.contains("홍길동"));
        assertEquals("홍길동", PiiCrypto.openText(KP.getPrivate(), enc));
        assertEquals(0, jdbc.queryForObject(
                "SELECT COUNT(*) FROM defect WHERE owner LIKE '%홍%' OR finder LIKE '%김%'", Integer.class));
    }

    @Test
    void 응답에는_토큰_대신_마스킹값이_나가고_되돌려_보내도_같은_사람이다() throws Exception {
        defects.create(Map.of("defectId", "D-1", "owner", "홍길동"));
        String token = ownerInDb("D-1");

        String body = http.writeValueAsString(defects.list(null, null, null, null));
        assertFalse(body.contains("PII-"), "토큰이 화면에 새면 안 된다: " + body);
        assertFalse(body.contains("홍길동"), "reveal=false 면 원문도 안 된다");
        String shown = "홍*동#" + token.substring(4, 10);
        assertTrue(body.contains(shown), body);

        defects.update("D-1", Map.of("owner", shown));   // 수정 폼이 받은 값을 그대로 다시 보냄
        assertEquals(token, ownerInDb("D-1"));
        defects.update("D-1", Map.of("owner", "홍길동"));  // 원문으로 다시 입력해도 같은 사람
        assertEquals(token, ownerInDb("D-1"));
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM pii_vault", Integer.class));
    }

    @Test
    void 이름_전체로_검색하면_찾는다() {
        defects.create(Map.of("defectId", "D-1", "owner", "홍길동", "content", "a"));
        defects.create(Map.of("defectId", "D-2", "owner", "김철수", "content", "b"));
        List<Map<String, Object>> hit = defects.list(null, "홍길동", null, null);
        assertEquals(List.of("D-1"), hit.stream().map(r -> r.get("defect_id")).toList());
    }

    @Test
    void 업로드_시트는_담당자_칸만_토큰이고_고유식별정보는_저장하지_않는다() {
        datasets.write("DS-P", "투입인력", "S", "f.xlsx", null, List.of("화면명", "담당자", "비고"),
                List.of(Map.of("화면명", "로그인", "담당자", "홍길동", "비고", "주민 900101-1234567")));

        String payload = jdbc.queryForObject("SELECT payload FROM dataset_row WHERE dataset_id='DS-P'", String.class);
        assertFalse(payload.contains("홍길동"), payload);
        assertFalse(payload.contains("900101"), payload);
        assertTrue(payload.contains("로그인"), "개인정보가 아닌 칸은 그대로");
        assertTrue(payload.contains(DatasetWriter.P3_BLOCKED));
        assertEquals(0, jdbc.queryForObject(
                "SELECT COUNT(*) FROM dataset_column WHERE min_v LIKE '%홍%' OR max_v LIKE '%홍%'", Integer.class),
                "컬럼 프로파일(min/max)로 원문이 새면 안 된다");
        assertTrue(datasets.findRow("DS-P", "담당자", "홍길동") >= 0, "원문으로 행을 찾을 수 있다");
    }

    @Test
    void 기존_평문은_전환_API가_토큰으로_바꾸고_두번_돌려도_같다() {
        jdbc.update("INSERT INTO defect (defect_id, owner, finder, source) VALUES ('D-OLD','이영희','박민수','excel')");
        jdbc.update("INSERT INTO defect (defect_id, owner, finder, source) VALUES ('D-ROLE','고객사,최지훈','기획','excel')");
        jdbc.update("INSERT INTO dataset (dataset_id, name, row_count, col_count) VALUES ('DS-OLD','x',1,1)");
        jdbc.update("INSERT INTO dataset_column (dataset_id, col_no, name, min_v, max_v) VALUES ('DS-OLD',0,'담당자','이영희','이영희')");
        jdbc.update("INSERT INTO dataset_row (dataset_id, row_no, payload) VALUES ('DS-OLD',0,'{\"담당자\":\"이영희\"}')");

        @SuppressWarnings("unchecked")
        Map<String, Integer> plain = (Map<String, Integer>) migration.status().get("plaintext");
        assertEquals(2, plain.get("defect.owner"), "이영희 + 고객사,최지훈 (역할어 finder '기획'은 변환 대상 아님)");
        assertEquals(1, plain.get("defect.finder"));

        Map<String, Object> first = migration.migrate();
        assertTrue(PiiCrypto.isToken(ownerInDb("D-OLD")));
        String payload = jdbc.queryForObject("SELECT payload FROM dataset_row WHERE dataset_id='DS-OLD'", String.class);
        assertFalse(payload.contains("이영희"));
        assertEquals(0, jdbc.queryForObject("SELECT COUNT(*) FROM dataset_column WHERE min_v IS NOT NULL", Integer.class));

        @SuppressWarnings("unchecked")
        Map<String, Integer> again = (Map<String, Integer>) migration.migrate().get("changed");
        assertTrue(again.values().stream().allMatch(n -> n == 0), "멱등이어야 한다: " + again);
        assertTrue(first.containsKey("changed"));
    }

    @Test
    void 복합값은_사람_조각만_토큰이고_역할어는_그대로다() throws Exception {
        defects.create(Map.of("defectId", "D-1", "owner", "고객사,홍길동", "finder", "기획"));
        String owner = ownerInDb("D-1");
        assertTrue(owner.startsWith("고객사,PII-"), owner);
        assertEquals("기획", jdbc.queryForObject("SELECT finder FROM defect WHERE defect_id='D-1'", String.class),
                "역할어는 사람이 아니다 — 마스킹하면 화면만 망가진다");
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM pii_vault", Integer.class), "금고엔 사람 1명만");

        String shown = http.writeValueAsString(defects.list(null, null, null, null));
        String display = shown.substring(shown.indexOf("고객사,홍*동#"), shown.indexOf("고객사,홍*동#") + 14);   // "고객사,홍*동#" + 토큰 앞 6자리
        defects.update("D-1", Map.of("owner", display));
        assertEquals(owner, ownerInDb("D-1"), "복합값 표시를 되돌려 보내도 같은 값");
        assertEquals(List.of("D-1"), defects.list(null, "홍길동", null, null).stream().map(r -> r.get("defect_id")).toList(),
                "복합값 안의 사람도 이름으로 찾는다");
    }

    @Test
    void 본문과_헤더_속_금고_인물은_토큰으로_바뀌고_응답에선_마스킹된다() throws Exception {
        defects.create(Map.of("defectId", "D-1", "owner", "홍길동"));
        defects.create(Map.of("defectId", "D-2", "content", "홍길동님 확인 후 재배포", "owner", "김철수"));
        String content = jdbc.queryForObject("SELECT content FROM defect WHERE defect_id='D-2'", String.class);
        assertFalse(content.contains("홍길동"), content);
        assertTrue(content.endsWith("님 확인 후 재배포"), "이름 외 본문은 그대로: " + content);
        String body = http.writeValueAsString(defects.list(null, null, null, null));
        assertTrue(body.contains("홍*동#") && body.contains("님 확인 후 재배포"), body);

        datasets.write("DS-M", "배치표", "S", "f.xlsx", null, List.of("화면", "홍길동"),
                List.of(Map.of("화면", "로그인", "홍길동", "O")));
        assertEquals(0, jdbc.queryForObject("SELECT COUNT(*) FROM dataset_column WHERE name LIKE '%홍길동%'", Integer.class),
                "사람 이름이 헤더인 시트(인력 배치표)");
        String payload = jdbc.queryForObject("SELECT payload FROM dataset_row WHERE dataset_id='DS-M'", String.class);
        assertFalse(payload.contains("홍길동"), payload);
        assertTrue(payload.contains("\"O\""));
    }

    @Test
    void 전환은_본문_속_이름까지_바꾼다() {
        jdbc.update("INSERT INTO defect (defect_id, owner, content, source) VALUES ('D-A','이영희','이영희 요청 반영','excel')");
        jdbc.update("INSERT INTO defect (defect_id, owner, content, source) VALUES ('D-B','박민수','박민수→이영희 이관','excel')");
        migration.migrate();
        assertEquals(0, jdbc.queryForObject(
                "SELECT COUNT(*) FROM defect WHERE content LIKE '%이영희%' OR content LIKE '%박민수%'", Integer.class));
        assertEquals(0, ((Map<?, ?>) migration.migrate().get("changed")).values().stream()
                .filter(n -> ((Integer) n) != 0).count(), "멱등");
    }

    @Test
    void 처리된_업로드_원본은_봉인되고_평문은_지워진다() throws Exception {
        Path dir = Files.createTempDirectory("pii-up");
        Path plain = dir.resolve("UP-1_홍길동_명단.xlsx");
        Files.write(plain, "PK 원본 바이트".getBytes());
        byte[] orig = Files.readAllBytes(plain);

        Path sealed = vault.sealStored(plain, null);
        assertFalse(Files.exists(plain), "평문이 남으면 안 된다");
        assertTrue(sealed.toString().endsWith(".sealed") && PiiCrypto.isSealedFile(sealed));
        var out = new java.io.ByteArrayOutputStream();
        try (var in = Files.newInputStream(sealed)) { PiiCrypto.openFile(KP.getPrivate(), in, out); }
        org.junit.jupiter.api.Assertions.assertArrayEquals(orig, out.toByteArray());
        assertEquals(sealed, vault.sealStored(sealed, null), "이미 봉인된 파일은 그대로");
    }

    @Test
    void 전환은_기존_원본을_봉인하고_평문은_보류_폴더로_옮기며_이력_경로를_바꾼다() throws Exception {
        Path root = DIR;
        Path uploads = Files.createDirectories(root.resolve("uploads"));
        Path plain = uploads.resolve("UP-9_명단.xlsx");
        Files.writeString(plain, "원본");
        jdbc.update("DELETE FROM upload_batch");
        jdbc.update("INSERT INTO upload_batch (batch_id, kind, file_name, stored_path, uploaded_at) VALUES ('UP-9','dataset','명단.xlsx',?,'2026-09-24')",
                plain.toAbsolutePath().toString());
        jdbc.update("INSERT INTO source_fragment (frag_id, doc_id, seq, locator, kind, text) VALUES ('X#1','X',1,'txt:L1','text','홍길동 검토')");
        defects.create(Map.of("defectId", "D-1", "owner", "홍길동"));
        try {
            Map<?, ?> changed = (Map<?, ?>) migration.migrate().get("changed");
            assertEquals(1, changed.get("sealed_files"));
            assertFalse(Files.exists(plain));
            assertTrue(Files.exists(uploads.resolve("UP-9_명단.xlsx.sealed")));
            assertTrue(Files.exists(root.resolve("hold").resolve("uploads").resolve("UP-9_명단.xlsx")), "평문은 보류 폴더로");
            assertTrue(jdbc.queryForObject("SELECT stored_path FROM upload_batch WHERE batch_id='UP-9'", String.class).endsWith(".sealed"));
            assertFalse(jdbc.queryForObject("SELECT text FROM source_fragment WHERE frag_id='X#1'", String.class).contains("홍길동"),
                    "원본 자료 조각 본문도 치환한다");
            assertEquals(0, ((Map<?, ?>) migration.migrate().get("changed")).get("sealed_files"), "멱등");
        } finally {
            jdbc.update("DELETE FROM source_fragment");
        }
    }

    @Test
    void 금고를_열_수_없으면_전환하지_않는다() {
        // 같은 JVM 의 다른 금고: 색인키만 있고 개인키가 없다
        PiiVault noPriv = new PiiVault(jdbc, "file:" + DIR.resolve("pub.pem"), PiiCrypto.newIndexKey(), "", false);
        assertThrows(IllegalStateException.class, noPriv::verifyRoundTrip);
        assertTrue(vault.canDecrypt());
    }
}
