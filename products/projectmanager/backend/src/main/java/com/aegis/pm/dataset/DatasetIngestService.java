package com.aegis.pm.dataset;

import java.io.File;
import java.io.FileInputStream;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;

import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.aegis.pm.excel.Cells;
import com.aegis.pm.excel.Workbooks;

/**
 * 어떤 엑셀이든 받아 데이터로 만든다.
 *
 * 파일명·시트명에 기대지 않는다 — 시트마다 헤더 행을 스스로 찾고, 값에서 컬럼 타입을 추론해
 * dataset / dataset_column / dataset_row 로 적재한다. 이후 조회·집계·화면 구성은 전부 DB에서 한다.
 */
@Service
public class DatasetIngestService {

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final DateTimeFormatter ID_TS = DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss");
    /** 헤더로 인정할 최소 컬럼 수 — 표지·제목 행이 헤더로 잡히는 것을 막는다 */
    private static final int MIN_HEADER_COLS = 2;
    /** 헤더를 찾을 때 훑어볼 상단 행 수 */
    /** 컬럼명 길이 상한 — 셀 하나에 문단이 통째로 들어있는 시트가 실제로 있다(DB 컬럼 길이 초과 방지) */
    private static final int MAX_NAME = 180;

    private final JdbcTemplate jdbc;
    private final DatasetWriter writer;

    public DatasetIngestService(JdbcTemplate jdbc, DatasetWriter writer) {
        this.jdbc = jdbc;
        this.writer = writer;
    }

    /** 시트 하나를 표로 읽을 수 있는지 — 업로드 라우팅이 미리 확인할 때 쓴다 */
    public boolean readable(Sheet sheet) {
        return parse(Workbooks.toGrid(sheet)) != null;
    }

    /** 시트 하나를 지정한 ID로 적재 (Core 부속 시트가 고정 ID를 쓴다) */
    @Transactional
    public int ingestSheet(String datasetId, String name, Sheet sheet, String fileName, String batchId) {
        Parsed p = parse(Workbooks.toGrid(sheet));
        if (p == null) return 0;
        return writer.write(datasetId, name, sheet.getSheetName(), fileName, batchId, p.headers(), p.rows());
    }

    /** 엑셀 1개 → 데이터가 있는 모든 시트를 데이터셋으로 적재 */
    @Transactional
    public List<Map<String, Object>> ingest(File file, String fileName, String batchId) {
        List<Map<String, Object>> made = new ArrayList<>();
        String stamp = LocalDateTime.now().format(ID_TS);
        int n = 0;

        try (FileInputStream in = new FileInputStream(Workbooks.resolve(file));
             Workbook wb = new XSSFWorkbook(in)) {
            for (int i = 0; i < wb.getNumberOfSheets(); i++) {
                Sheet sheet = wb.getSheetAt(i);
                Object[][] grid = Workbooks.toGrid(sheet);
                Parsed p = parse(grid);
                if (p == null) continue;   // 표·데이터가 없는 시트는 건너뛴다

                String datasetId = "DS-" + stamp + "-" + (++n);
                writer.write(datasetId, sheet.getSheetName(), sheet.getSheetName(),
                        fileName, batchId, p.headers(), p.rows());
                made.add(summary(datasetId));
            }
        } catch (Exception e) {
            throw new IllegalStateException("엑셀 판독 실패(" + fileName + "): " + e.getMessage(), e);
        }

        if (made.isEmpty()) {
            throw new IllegalArgumentException("표로 읽을 수 있는 시트를 찾지 못했습니다: " + fileName);
        }
        return made;
    }

    // ── 파싱 ────────────────────────────────────────────────────────────────

    private record Parsed(List<String> headers, List<Map<String, String>> rows) {}

    /** 헤더 행을 스스로 찾고 그 아래를 데이터로 읽는다 (표지·제목 행 건너뜀) */
    private Parsed parse(Object[][] g) {
        if (g == null || g.length == 0) return null;

        // 헤더 행은 통계로 고른다(엔진 HeaderDetector) — "2칸 이상 채워진 첫 행"은 제목 행·데이터 행을 헤더로 잡았다
        // (실측: WBS_미완료·서버정보 시트의 첫 데이터 행이 헤더가 됨). 헤더가 없다고 판정되면 첫 행부터 데이터다.
        List<List<String>> grid = new ArrayList<>(g.length);
        int width = 0;
        for (Object[] row : g) {
            List<String> cells = new ArrayList<>(row.length);
            for (Object c : row) cells.add(Cells.str(c));
            grid.add(cells);
            width = Math.max(width, row.length);
        }
        com.aegis.pm.engine.HeaderDetector.Result hd = com.aegis.pm.engine.HeaderDetector.detect(grid);
        int headerRow = hd.hasHeader() ? hd.row() : -1;
        int firstData = hd.hasHeader() ? hd.row() + 1 : 0;
        if (!hd.hasHeader()) {
            int filledMax = 0;
            for (Object[] row : g) { int f = 0; for (Object c : row) if (!Cells.str(c).isEmpty()) f++; filledMax = Math.max(filledMax, f); }
            if (filledMax < MIN_HEADER_COLS) return null;
        }

        // 중복·빈 헤더 보정 — 컬럼명을 키로 쓰므로 반드시 유일해야 한다
        List<String> headers = new ArrayList<>();
        LinkedHashSet<String> seen = new LinkedHashSet<>();
        Object[] head = headerRow >= 0 ? g[headerRow] : new Object[width];
        for (int c = 0; c < head.length; c++) {
            String name = cut(Cells.str(head[c]).replaceAll("\\s+", " ").trim(), MAX_NAME);
            if (name.isEmpty()) name = "col" + (c + 1);
            String base = name;
            int dup = 2;
            while (!seen.add(name)) name = base + "_" + dup++;
            headers.add(name);
        }

        List<Map<String, String>> rows = new ArrayList<>();
        for (int r = firstData; r < g.length; r++) {
            if (!hasValue(g[r])) continue;
            Map<String, String> row = new LinkedHashMap<>();
            for (int c = 0; c < headers.size(); c++) {
                String v = Cells.str(Cells.at(g[r], c));
                if (!v.isEmpty()) row.put(headers.get(c), v);
            }
            if (!row.isEmpty()) rows.add(row);
        }
        return rows.isEmpty() ? null : new Parsed(headers, rows);
    }

    private static String cut(String s, int n) {
        return s == null || s.length() <= n ? s : s.substring(0, n);
    }

    private static boolean hasValue(Object[] row) {
        if (row == null) return false;
        for (Object c : row) if (!Cells.str(c).isEmpty()) return true;
        return false;
    }

    // ── 저장 ────────────────────────────────────────────────────────────────

    private Map<String, Object> summary(String datasetId) {
        Map<String, Object> d = jdbc.queryForMap("SELECT * FROM dataset WHERE dataset_id = ?", datasetId);
        d.put("columns", jdbc.queryForList(
                "SELECT col_no, name, data_type, distinct_n, null_n, min_v, max_v, sum_v"
                        + " FROM dataset_column WHERE dataset_id = ? ORDER BY col_no", datasetId));
        return d;
    }

}
