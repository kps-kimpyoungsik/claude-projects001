package com.aegis.pm.source;

import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import com.aegis.pm.common.Rows;
import com.aegis.pm.upload.UploadService;

/**
 * 비정형 자료 입구 (USS U1 + G1).
 *
 * <p>기존 엑셀 업로드({@code /api/uploads})는 <b>건드리지 않는다</b> — 그쪽은 표를 Core/Dataset 으로
 * 적재하고, 여기는 어떤 파일이든 원본 보관 + 조각·좌표로 편 뒤 L3 정형화를 기다리게 둔다.
 *
 * <h3>같은 원본은 한 번만 (T115 SSI)</h3>
 * sha256 이 같으면 새 문서를 만들지 않고 기존 문서를 돌려준다. 조각이 두 벌 생기면 이후 정형화된
 * 값의 출처가 둘로 갈라져 "어느 쪽이 근거인가"를 판정할 수 없다. 재업로드 사실 자체는
 * {@code case_usage} 에 남는다 — 사용 이력은 지우지 않는다.
 */
@Service
public class SourceService {

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final DateTimeFormatter ID_TS = DateTimeFormatter.ofPattern("yyyyMMdd-HHmmssSSS");
    private static final Path STORE = Paths.get("data", "sources");
    private static final int BATCH = 1000;

    private final JdbcTemplate jdbc;

    public SourceService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @Transactional
    public Map<String, Object> ingest(MultipartFile file) throws Exception {
        if (file == null || file.isEmpty()) throw new IllegalArgumentException("업로드된 파일이 없습니다.");
        String name = file.getOriginalFilename() == null ? "upload" : file.getOriginalFilename();
        UploadService.assertDecodableName(name);
        String format = Extractor.formatOf(name);
        if (!Extractor.supported(format)) {
            throw new IllegalArgumentException("지원하지 않는 형식입니다: " + name
                    + " — 문서(xlsx·docx·pptx·txt·md·csv) · 이미지 · 음성 · pdf 를 올릴 수 있습니다.");
        }

        Files.createDirectories(STORE);
        String stamp = LocalDateTime.now().format(ID_TS);
        String caseId = "SRC-" + stamp;
        Path stored = STORE.resolve(stamp + "_" + name.replaceAll("[\\\\/:*?\"<>|]", "_"));
        try (InputStream in = file.getInputStream()) {
            Files.copy(in, stored, StandardCopyOption.REPLACE_EXISTING);
        }
        String now = LocalDateTime.now().format(TS);

        try {
            assertContainer(stored, format, name);
            String sha = sha256(stored);
            List<Map<String, Object>> dup = jdbc.queryForList(
                    "SELECT doc_id, frag_count FROM source_doc WHERE sha256 = ?", sha);
            if (!dup.isEmpty()) {
                Files.deleteIfExists(stored);
                Map<String, Object> d = Rows.lower(dup.get(0));
                String docId = (String) d.get("doc_id");
                recordUsage(caseId, "source_doc", docId, "input", now);
                return result(caseId, docId, name, format, ((Number) d.get("frag_count")).intValue(), true);
            }

            String docId = "DOC-" + stamp;
            jdbc.update("""
                    INSERT INTO source_doc (doc_id, file_name, format, sha256, stored_path, size_bytes,
                                            frag_count, uploaded_at)
                    VALUES (?,?,?,?,?,?,0,?)
                    """, docId, name, format, sha, stored.toAbsolutePath().toString(), Files.size(stored), now);
            // 조각을 리스트로 모으지 않고 BATCH 건씩 흘려 넣는다 — 큰 시트에서 힙에 전부 올리지 않기 위해
            List<Object[]> buf = new ArrayList<>(BATCH);
            int[] seq = { 0 };
            Extractor.extract(stored, format, f -> {
                seq[0]++;
                buf.add(new Object[] { docId + "#" + seq[0], docId, seq[0], f.locator(), f.kind(),
                        f.text(), f.confidence() });
                if (buf.size() == BATCH) flush(buf);
            });
            flush(buf);
            jdbc.update("UPDATE source_doc SET frag_count = ? WHERE doc_id = ?", seq[0], docId);
            recordUsage(caseId, "source_doc", docId, "input", now);
            return result(caseId, docId, name, format, seq[0], false);
        } catch (Exception e) {
            // 실패한 원본을 남기면 data/sources 가 재처리 대상으로 오인되는 쓰레기로 찬다
            Files.deleteIfExists(stored);
            throw e;
        }
    }

    private void flush(List<Object[]> buf) {
        if (buf.isEmpty()) return;
        jdbc.batchUpdate("""
                INSERT INTO source_fragment (frag_id, doc_id, seq, locator, kind, text, confidence)
                VALUES (?,?,?,?,?,?,?)
                """, buf);
        buf.clear();
    }

    /**
     * G1 — 어떤 작업(case)이 어떤 노드를 입력·참조·산출로 썼는가.
     * 지금부터 쌓지 않으면 과거 사용 이력은 복원할 수 없다(20번 §9). 본 적재와 같은 트랜잭션에
     * 묶는다 — "기록 없는 적재"가 생기면 이력이 빈 채로 정상처럼 보인다.
     * case_id 는 호출마다 새로 만들므로 PK 충돌이 없다(H2·PostgreSQL 공통 SQL 만 쓴다).
     */
    public void recordUsage(String caseId, String nodeType, String nodeId, String usage, String at) {
        jdbc.update("INSERT INTO case_usage (case_id, node_type, node_id, usage, used_at) VALUES (?,?,?,?,?)",
                caseId, nodeType, nodeId, usage, at);
    }

    public List<Map<String, Object>> docs() {
        return Rows.lower(jdbc.queryForList("SELECT * FROM source_doc ORDER BY uploaded_at DESC, doc_id DESC"));
    }

    /** 앞에서부터 limit 개 — 조각이 수백만 개인 시트를 화면에 통째로 보내지 않는다 */
    public List<Map<String, Object>> fragments(String docId, int limit) {
        return Rows.lower(jdbc.queryForList(
                "SELECT frag_id, seq, locator, kind, text, confidence FROM source_fragment WHERE doc_id = ? ORDER BY seq LIMIT ?",
                docId, Math.max(1, Math.min(limit, 5000))));
    }

    /** 오피스 3종은 ZIP 컨테이너 — 확장자만 바꾼 파일은 POI 500 대신 사유가 분명한 400 으로 */
    static void assertContainer(Path f, String format, String name) throws Exception {
        if (!Extractor.OFFICE.contains(format)) {
            if (Files.size(f) == 0) throw new IllegalArgumentException("빈 파일입니다: " + name);
            return;
        }
        byte[] head = new byte[4];
        int n;
        try (InputStream in = Files.newInputStream(f)) {
            n = in.read(head);
        }
        if (n == 4 && head[0] == 'P' && head[1] == 'K' && head[2] == 3 && head[3] == 4) return;
        throw new IllegalArgumentException(format + " 형식이 아닙니다(내용 확인): " + name);
    }

    private static String sha256(Path f) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        try (InputStream in = Files.newInputStream(f)) {
            byte[] buf = new byte[8192];
            for (int n; (n = in.read(buf)) > 0; ) md.update(buf, 0, n);
        }
        return HexFormat.of().formatHex(md.digest());
    }

    private static Map<String, Object> result(String caseId, String docId, String name, String format,
                                              int frags, boolean duplicate) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ok", true);
        out.put("caseId", caseId);
        out.put("docId", docId);
        out.put("fileName", name);
        out.put("format", format);
        out.put("fragments", frags);
        out.put("duplicate", duplicate);
        return out;
    }
}
