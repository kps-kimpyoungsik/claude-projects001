package com.aegis.pm.repo;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Repository;

import com.aegis.pm.domain.WbsModel;
import com.aegis.pm.excel.SheetTableReader;
import com.aegis.pm.excel.SheetTableReader.Table;
import com.aegis.pm.excel.WbsExcelReader;

/**
 * 엑셀 어댑터 (기본).
 * 파일 mtime이 바뀌면 ExcelSource가 자동으로 다시 읽으므로 "엑셀 저장 = 즉시 반영"이 유지된다.
 */
@Repository
@ConditionalOnProperty(name = "wbs.source", havingValue = "excel", matchIfMissing = true)
public class ExcelWbsRepository implements WbsRepository {

    private final WbsExcelReader reader;
    private final SheetTableReader tables;

    public ExcelWbsRepository(WbsExcelReader reader, SheetTableReader tables) {
        this.reader = reader;
        this.tables = tables;
    }

    @Override
    public WbsModel model() {
        return reader.read();
    }

    @Override
    public Table table(String logical) {
        return switch (logical) {
            case "issues" -> tables.read("이슈페이지", "이슈", "이슈이력관리");
            case "staffing" -> tables.read("투입인력현황");
            default -> new SheetTableReader.Table(false, java.util.List.of(), java.util.List.of());
        };
    }

    @Override
    public String describe() {
        return "excel";
    }
}
