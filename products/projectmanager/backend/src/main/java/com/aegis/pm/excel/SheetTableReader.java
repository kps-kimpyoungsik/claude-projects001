package com.aegis.pm.excel;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;

import com.aegis.pm.excel.Workbooks;

/**
 * 헤더 기반 제너릭 시트 판독 — Apps Script getIssuesJson()의 "첫 유효행=헤더, 이후=데이터" 규칙 이관.
 * 컬럼 구조가 바뀌어도 헤더 기준으로 자동 매핑한다(컬럼 하드코딩 금지).
 */
@Component
public class SheetTableReader {

    public record Table(boolean found, List<String> headers, List<Map<String, String>> rows) {
        static Table empty(boolean found) { return new Table(found, List.of(), List.of()); }
    }

    private final ExcelSource source;

    public SheetTableReader(ExcelSource source) { this.source = source; }

    /** 업로드된 파일에서 직접 읽는다 — 설정 원본 경로에 의존하지 않는다 */
    public Table read(java.io.File file, String... sheetNameCandidates) {
        return parse(Workbooks.grid(file, sheetNameCandidates));
    }

    public Table read(String... sheetNameCandidates) {
        return parse(source.grid(sheetNameCandidates));
    }

    private Table parse(Object[][] data) {
        if (data == null || data.length == 0) return Table.empty(false);

        int hi = firstNonEmptyRow(data);
        if (hi < 0) return Table.empty(true);

        Object[] headerRow = data[hi];
        List<Integer> idx = new ArrayList<>();
        List<String> names = new ArrayList<>();
        for (int c = 0; c < headerRow.length; c++) {
            String h = Cells.str(headerRow[c]);
            if (!h.isEmpty()) { idx.add(c); names.add(h); }
        }

        List<Map<String, String>> rows = new ArrayList<>();
        for (int r = hi + 1; r < data.length; r++) {
            Object[] row = data[r];
            if (isEmpty(row)) continue;
            Map<String, String> obj = new LinkedHashMap<>();
            for (int k = 0; k < idx.size(); k++) obj.put(names.get(k), Cells.str(Cells.at(row, idx.get(k))));
            rows.add(obj);
        }
        return new Table(true, names, rows);
    }

    private static int firstNonEmptyRow(Object[][] data) {
        for (int r = 0; r < data.length; r++) if (!isEmpty(data[r])) return r;
        return -1;
    }

    private static boolean isEmpty(Object[] row) {
        if (row == null) return true;
        for (Object c : row) if (!Cells.str(c).isEmpty()) return false;
        return true;
    }
}
