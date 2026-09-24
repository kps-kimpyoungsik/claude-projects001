package com.aegis.pm.excel;

import java.io.File;
import java.io.FileInputStream;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;

import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.CellType;
import org.apache.poi.ss.usermodel.DateUtil;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;

/** 엑셀 → 0-based 격자 판독 공통 로직 (ExcelSource / 단위테스트 적재가 함께 쓴다) */
public final class Workbooks {

    private Workbooks() {}

    /**
     * 설정 경로가 정확히 없을 때 같은 폴더에서 이름이 근접한 파일을 찾는다.
     * 실제로 원본 파일 이름 앞에 접두사가 붙는 일이 있었다(예: `_이름.xlsx`) — 그때마다 설정을
     * 고치는 대신, 파일명이 끝부분만 일치해도 같은 파일로 본다.
     */
    public static File resolve(File file) {
        if (file.exists()) return file;
        File dir = file.getParentFile();
        String want = file.getName();
        if (dir != null && dir.isDirectory()) {
            // ~$ 로 시작하는 건 엑셀이 파일을 열어둘 때 만드는 임시 잠금 파일이다 — 후보에서 뺀다
            File[] found = dir.listFiles((d, n) ->
                    !n.startsWith("~$") && (n.endsWith(want) || want.endsWith(n)));
            if (found != null && found.length == 1) return found[0];
        }
        return file;
    }

    /** 지정 파일에서 후보 시트명 중 먼저 찾히는 시트를 격자로 읽는다. 없으면 null */
    public static Object[][] grid(File requested, String... sheetNameCandidates) {
        File file = resolve(requested);
        if (!file.exists()) throw new IllegalStateException("엑셀 파일을 찾을 수 없습니다: " + requested);
        try (FileInputStream in = new FileInputStream(file); Workbook wb = new XSSFWorkbook(in)) {
            Sheet sheet = null;
            for (String name : sheetNameCandidates) {
                if (name == null || name.isBlank()) continue;
                sheet = wb.getSheet(name);
                if (sheet != null) break;
            }
            if (sheet == null) return null;
            return toGrid(sheet);
        } catch (Exception e) {
            throw new IllegalStateException("엑셀 판독 실패(" + file.getName() + "): " + e.getMessage(), e);
        }
    }

    public static Object[][] toGrid(Sheet sheet) {
        int lastRow = sheet.getLastRowNum();
        int width = 0;
        for (int r = 0; r <= lastRow; r++) {
            Row row = sheet.getRow(r);
            if (row != null) width = Math.max(width, row.getLastCellNum());
        }
        List<Object[]> out = new ArrayList<>();
        for (int r = 0; r <= lastRow; r++) {
            Object[] cells = new Object[Math.max(width, 1)];
            Row row = sheet.getRow(r);
            if (row != null) {
                for (int c = 0; c < width; c++) cells[c] = value(row.getCell(c));
            }
            out.add(cells);
        }
        return out.toArray(new Object[0][]);
    }

    /** 셀 → String / Double / LocalDate (수식 셀은 캐시된 계산 결과 사용) */
    public static Object value(Cell cell) {
        if (cell == null) return null;
        CellType type = cell.getCellType() == CellType.FORMULA ? cell.getCachedFormulaResultType() : cell.getCellType();
        switch (type) {
            case STRING:
                String s = cell.getStringCellValue();
                return s == null || s.isBlank() ? null : s.trim();
            case NUMERIC:
                if (DateUtil.isCellDateFormatted(cell)) {
                    Date d = cell.getDateCellValue();
                    return d == null ? null : LocalDate.ofInstant(d.toInstant(), ZoneId.systemDefault());
                }
                return cell.getNumericCellValue();
            case BOOLEAN:
                return cell.getBooleanCellValue();
            default:
                return null;
        }
    }
}
