package com.aegis.pm.upload;

import com.aegis.pm.common.Rows;
import java.io.File;
import java.io.FileInputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import com.aegis.pm.dataset.DatasetIngestService;
import com.aegis.pm.repo.WbsImportService;
import com.aegis.pm.unittest.IaImportService;

/**
 * 엑셀 업로드 창구 — **하나뿐이다.**
 *
 * 파일을 시트 단위로 훑어 각 시트를 어디로 보낼지 스스로 정한다.
 *   알려진 도메인 시트(WBS_Raw · PC_IA(화면목록) · 기획요청-결함…) → Core 적재(계산 로직이 붙는 영역)
 *   그 밖의 모든 시트                                              → Dataset 적재(동적 대시보드)
 * 어느 시트가 어디로 갔는지는 응답과 upload_batch 에 그대로 남는다 — 사용자가 종류를 고를 필요가 없다.
 */
@Service
public class UploadService {

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final DateTimeFormatter ID_TS = DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss");
    private static final Path STORE = Paths.get("data", "uploads");

    private final WbsImportService wbsImporter;
    private final IaImportService iaImporter;
    private final DatasetIngestService datasetIngest;
    private final JdbcTemplate jdbc;
    private final com.aegis.pm.pii.PiiVault pii;
    private static final org.slf4j.Logger log = org.slf4j.LoggerFactory.getLogger(UploadService.class);

    public UploadService(WbsImportService wbsImporter, IaImportService iaImporter,
                         DatasetIngestService datasetIngest, JdbcTemplate jdbc, com.aegis.pm.pii.PiiVault pii) {
        this.pii = pii;
        this.wbsImporter = wbsImporter;
        this.iaImporter = iaImporter;
        this.datasetIngest = datasetIngest;
        this.jdbc = jdbc;
    }

    /** 시트 1개의 처리 결과 */
    private record Routed(String sheet, String target, String detail, int added, int updated,
                          int unchanged, int kept) {}

    @Transactional
    public Map<String, Object> upload(MultipartFile file) throws Exception {
        if (file == null || file.isEmpty()) throw new IllegalArgumentException("업로드된 파일이 없습니다.");
        String name = file.getOriginalFilename() == null ? "upload.xlsx" : file.getOriginalFilename();
        if (!name.toLowerCase().endsWith(".xlsx")) {
            throw new IllegalArgumentException("xlsx 파일만 올릴 수 있습니다: " + name);
        }
        assertDecodableName(name);

        Files.createDirectories(STORE);
        String batchId = "UP-" + LocalDateTime.now().format(ID_TS);
        Path stored = STORE.resolve(batchId + "_" + name.replaceAll("[\\\\/:*?\"<>|]", "_"));
        try (var in = file.getInputStream()) {
            Files.copy(in, stored, StandardCopyOption.REPLACE_EXISTING);
        }
        File f = stored.toFile();
        assertXlsx(f, name, stored);
        String now = LocalDateTime.now().format(TS);

        List<Routed> routed = route(f, name, batchId);
        if (routed.isEmpty()) {
            throw new IllegalArgumentException("표로 읽을 수 있는 시트가 없습니다: " + name);
        }

        int added = routed.stream().mapToInt(Routed::added).sum();
        int updated = routed.stream().mapToInt(Routed::updated).sum();
        int unchanged = routed.stream().mapToInt(Routed::unchanged).sum();
        int kept = routed.stream().mapToInt(Routed::kept).sum();
        String kind = kindOf(routed);
        String note = routed.stream().map(r -> r.sheet() + "→" + r.target()).reduce((a, b) -> a + ", " + b).orElse("");

        jdbc.update("""
                INSERT INTO upload_batch (batch_id, kind, file_name, stored_path, uploaded_at,
                                          added, updated, unchanged, kept, note)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """, batchId, kind, name, stored.toAbsolutePath().toString(), now,
                added, updated, unchanged, kept, cut(note, 1000));
        for (Routed r : routed) {
            if (r.target().startsWith("core:")) usage(batchId, "core", r.target().substring(5));
        }
        // 원본은 적재 후 다시 읽지 않는다 — 봉인하고 평문을 지운다 (pii 설계서 §8 2단계, 지침 G-9).
        // 봉인이 실패해도 적재는 되돌리지 않는다(이미 성공한 반영을 잃는 쪽이 더 나쁘다) — 경고만 남긴다.
        boolean sealed = false;
        try {
            Path s = pii.sealStored(stored, null);
            if (!s.equals(stored)) {
                jdbc.update("UPDATE upload_batch SET stored_path = ? WHERE batch_id = ?", s.toAbsolutePath().toString(), batchId);
                sealed = true;
            }
        } catch (Exception e) {
            log.warn("[개인정보] 업로드 원본 봉인 실패 batch={} — 평문 보관 중 ({})", batchId, e.getClass().getSimpleName());
        }

        List<Map<String, Object>> sheets = new ArrayList<>();
        for (Routed r : routed) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("sheet", r.sheet());
            m.put("target", r.target());
            m.put("detail", r.detail());
            m.put("added", r.added());
            m.put("updated", r.updated());
            m.put("unchanged", r.unchanged());
            m.put("kept", r.kept());
            sheets.add(m);
        }

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ok", true);
        out.put("batchId", batchId);
        out.put("kind", kind);
        out.put("fileName", name);
        out.put("uploadedAt", now);
        out.put("sealed", sealed);
        out.put("sheets", sheets);
        out.put("added", added);
        out.put("updated", updated);
        out.put("unchanged", unchanged);
        out.put("kept", kept);
        out.put("note", note);
        return out;
    }

    /**
     * 파일명이 <b>깨진 채로</b> 들어오면 거절한다 — 저장하면 화면에 영구히 깨져 보인다.
     *
     * <h3>왜 복원하지 않고 거절하는가</h3>
     * 깨진 이름에는 {@code U+FFFD}(대체문자)가 들어 있다. 이 문자는 "디코딩에 실패해 원본
     * 바이트를 버렸다"는 표식이다 — <b>버려진 바이트는 되돌릴 수 없다.</b> 실측(2026-09-19):
     * `_작업확인-개발WBS_…xlsx` 가 U+FFFD 20개짜리 문자열로 적재돼 `/data/sources` 화면에
     * 깨져 보였다. 추측으로 복원하면 틀린 이름을 사실처럼 저장하게 되므로 거절이 정직하다.
     *
     * <h3>누가 이렇게 보내는가</h3>
     * 브라우저는 파일명을 UTF-8 로 보내므로 정상이다. 깨지는 쪽은 <b>UTF-8 이 아닌 콘솔에서
     * 부른 CLI</b>(Git Bash/CP949 환경의 curl 등)다. 즉 서버 버그가 아니라 <b>호출자</b> 문제이고,
     * 그래서 서버가 할 일은 "고치기"가 아니라 "받지 않기"다.
     *
     * <p>실패한 업로드의 저장 파일은 남기지 않는다(호출 시점상 아직 복사 전이다).
     */
    public static void assertDecodableName(String name) {
        if (name.indexOf('�') < 0) return;
        throw new IllegalArgumentException(
                "파일명 인코딩이 깨졌습니다(복원 불가): " + name
                + " — UTF-8 로 전송하는 클라이언트(브라우저 업로드 버튼)를 쓰거나, "
                + "CLI 라면 파일명을 영문으로 바꿔 올리십시오.");
    }

    /**
     * 확장자가 아니라 <b>내용</b>으로 xlsx 인지 본다.
     *
     * <p>확장자만 검사하면 이름만 {@code .xlsx} 로 바꾼 아무 파일이나 통과해 POI 에서 500 이 난다
     * (TODO P2 #9). xlsx 는 ZIP 컨테이너라 첫 4바이트가 항상 {@code PK} 다 — 이 4바이트가
     * 확장자보다 정직하다.
     *
     * <p>빈 ZIP({@code PK})·분할 ZIP({@code PK}) 도 거른다. 시그니처는 맞지만
     * 워크북이 없어서 어차피 파싱에 실패한다 — 여기서 걸러야 사유가 분명한 400 이 된다.
     *
     * <p>통과하지 못한 파일은 <b>보관하지 않는다.</b> 남겨 두면 {@code data/uploads/} 가 쓰레기로
     * 차고, 나중에 재처리 대상으로 오인된다.
     */
    static void assertXlsx(File f, String name, Path stored) throws java.io.IOException {
        byte[] head = new byte[4];
        int n;
        try (FileInputStream in = new FileInputStream(f)) {
            n = in.read(head);
        }
        boolean zip = n == 4 && head[0] == 'P' && head[1] == 'K'
                && head[2] == 0x03 && head[3] == 0x04;
        if (zip) return;
        Files.deleteIfExists(stored);
        throw new IllegalArgumentException(
                "xlsx 형식이 아닙니다(내용 확인): " + name
                + " — 확장자만 xlsx 이거나 비어 있는 파일입니다.");
    }

    /** 시트별로 Core / Dataset 을 정해 적재한다 */
    private List<Routed> route(File f, String fileName, String batchId) throws Exception {
        List<Routed> out = new ArrayList<>();
        List<String> datasetSheets = new ArrayList<>();
        boolean wbsDone = false, iaDone = false, defectDone = false;

        try (FileInputStream in = new FileInputStream(f); Workbook wb = new XSSFWorkbook(in)) {
            for (int i = 0; i < wb.getNumberOfSheets(); i++) {
                Sheet sheet = wb.getSheetAt(i);
                String s = sheet.getSheetName();

                if (!wbsDone && (s.equalsIgnoreCase("WBS_Raw") || s.equalsIgnoreCase("WEB_Raw"))) {
                    // WBS 는 부속 시트(이슈·투입인력)까지 한 번에 처리한다
                    Map<String, Object> r = wbsImporter.importFrom(f);
                    out.add(new Routed(s, "core:wbs",
                            "작업 " + r.get("tasks") + "건 · 이슈 " + r.get("issueRows")
                                    + "건 · 투입인력 " + r.get("staffingRows") + "건 (전량 교체)",
                            (int) r.get("tasks"), 0, 0, 0));
                    wbsDone = true;
                } else if (!iaDone && (s.contains("PC_IA") || s.contains("화면목록")) && !s.contains("Mobile")
                        && hasHeader(sheet, "개발완료여부")) {
                    // 시트 이름만 같고 표가 전혀 다른 파일이 있다 — IA 필수 열이 없으면 Core 로 보내지 않는다
                    // (2026-09-08 실사고: '대응업무분장' 파일의 PC_IA 시트가 IA 화면목록 252건을 덮었다)
                    int n = iaImporter.importIa(f);
                    out.add(new Routed(s, "core:ia", "화면 " + n + "건 (전량 교체)", n, 0, 0, 0));
                    iaDone = true;
                } else if (!defectDone && (s.contains("기획요청") || s.contains("결함"))) {
                    Map<String, Object> r = iaImporter.importDefects(f, batchId);
                    out.add(new Routed(s, "core:defect",
                            "신규 " + r.get("added") + " · 변경 " + r.get("updated")
                                    + " · 동일 " + r.get("unchanged") + " · 화면등록 유지 " + r.get("kept"),
                            (int) r.get("added"), (int) r.get("updated"),
                            (int) r.get("unchanged"), (int) r.get("kept")));
                    defectDone = true;
                } else if (datasetIngest.readable(sheet)) {
                    datasetSheets.add(s);
                }
            }
        }

        // 나머지 시트는 데이터셋으로 (같은 파일을 다시 열어 ID를 이어서 붙인다)
        if (!datasetSheets.isEmpty()) {
            String stamp = LocalDateTime.now().format(ID_TS);
            int n = 0;
            try (FileInputStream in = new FileInputStream(f); Workbook wb = new XSSFWorkbook(in)) {
                for (String s : datasetSheets) {
                    Sheet sheet = wb.getSheet(s);
                    if (sheet == null) continue;
                    String datasetId = "DS-" + stamp + "-" + (++n);
                    int rows = datasetIngest.ingestSheet(datasetId, s, sheet, fileName, batchId);
                    if (rows > 0) {
                        out.add(new Routed(s, "dataset", rows + "행 · " + datasetId, rows, 0, 0, 0));
                        usage(batchId, "dataset", datasetId);
                    }
                }
            }
        }
        return out;
    }

    /** 시트 상단 20행 안에 그 헤더 문구가 있는가 — Core 오적재 방지용 최소 확인 */
    private static boolean hasHeader(Sheet sheet, String keyword) {
        int last = Math.min(sheet.getLastRowNum(), 20);
        for (int r = sheet.getFirstRowNum(); r <= last; r++) {
            var row = sheet.getRow(r);
            if (row == null) continue;
            for (var cell : row) {
                if (cell != null && cell.toString().contains(keyword)) return true;
            }
        }
        return false;
    }

    /** G1 case_usage — 이 업로드(case)가 어떤 데이터셋·Core 영역을 만들었나. 과거분은 복원할 수 없어 지금부터 쌓는다 */
    private void usage(String batchId, String nodeType, String nodeId) {
        jdbc.update("INSERT INTO case_usage (case_id, node_type, node_id, usage, used_at) VALUES (?,?,?,?,?)",
                batchId, nodeType, nodeId, "output", LocalDateTime.now().format(TS));
    }

    /** 업로드 이력 표시용 대표 종류 */
    private String kindOf(List<Routed> routed) {
        for (Routed r : routed) {
            if (r.target().startsWith("core:")) return r.target().substring(5);
        }
        return "dataset";
    }

    private static String cut(String s, int n) {
        return s == null || s.length() <= n ? s : s.substring(0, n);
    }

    public List<Map<String, Object>> batches(String kind) {
        if (kind == null || kind.isBlank()) {
            // 화면(`Defects.jsx`)은 `x.batch_id` 로 읽는다 — H2 대문자 키를 그대로 내보내면
            // 전 필드가 undefined 가 된다(오류 없이 빈 화면이라 더 오래 산다).
            return Rows.lower(jdbc.queryForList("SELECT * FROM upload_batch ORDER BY uploaded_at DESC, batch_id DESC"));
        }
        return Rows.lower(jdbc.queryForList(
                "SELECT * FROM upload_batch WHERE kind = ? ORDER BY uploaded_at DESC, batch_id DESC", kind));
    }

    /**
     * 특정 업로드가 건드린 결함 목록.
     * onlyNew=true 면 "그 업로드로 처음 들어온 건"만 — 별도 사이트(원본 대장)에서 추가된 내역이다.
     */
    public List<Map<String, Object>> batchDefects(String batchId, boolean onlyNew) {
        String sql = """
                SELECT defect_id, reg_dt, req_id, screen, def_type, severity, priority,
                       content, owner, status, source, batch_id, added_batch_id, created_at, updated_at
                  FROM defect WHERE %s ORDER BY defect_id
                """.formatted(onlyNew ? "added_batch_id = ?" : "batch_id = ?");
        List<Map<String, Object>> rows = jdbc.queryForList(sql, batchId);
        for (Map<String, Object> r : rows) {
            r.put("isNew", batchId.equals(String.valueOf(r.get("added_batch_id"))));
        }
        return rows;
    }
}
