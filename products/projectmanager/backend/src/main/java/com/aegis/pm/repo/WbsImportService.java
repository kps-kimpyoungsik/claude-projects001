package com.aegis.pm.repo;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.aegis.pm.config.WbsProperties;
import com.aegis.pm.dataset.CoreDatasets;
import com.aegis.pm.dataset.DatasetWriter;
import com.aegis.pm.domain.Task;
import com.aegis.pm.domain.WbsModel;
import com.aegis.pm.excel.ExcelSource;
import com.aegis.pm.excel.SheetTableReader;
import com.aegis.pm.excel.WbsExcelReader;

/**
 * 엑셀 → DB 적재.
 *
 * 이 클래스가 "엑셀에 의존하는 유일한 지점"이다. 적재를 끝내면 조회 경로(JdbcWbsRepository)는
 * 엑셀 파일 없이 동작하므로, 운영에서는 엑셀을 업로드 도구로만 쓰면 된다.
 * 적재는 전량 교체(delete → insert)다 — WBS는 행 순서 자체가 계층 정보라 부분 갱신이 위험하다.
 */
@Service
public class WbsImportService {

    private final WbsExcelReader reader;
    private final SheetTableReader tables;
    private final ExcelSource source;
    private final WbsProperties props;
    private final JdbcTemplate jdbc;
    private final DatasetWriter datasets;

    public WbsImportService(WbsExcelReader reader, SheetTableReader tables, ExcelSource source,
                            WbsProperties props, JdbcTemplate jdbc, DatasetWriter datasets) {
        this.reader = reader;
        this.tables = tables;
        this.source = source;
        this.props = props;
        this.jdbc = jdbc;
        this.datasets = datasets;
    }

    @Transactional
    public Map<String, Object> importAll() {
        return importFrom(null);
    }

    /** file=null 이면 설정된 원본, 아니면 업로드된 파일에서 적재한다 */
    @Transactional
    public Map<String, Object> importFrom(java.io.File file) {
        WbsModel m = (file == null) ? reader.read() : reader.read(file);

        jdbc.update("DELETE FROM wbs_task");
        jdbc.update("DELETE FROM wbs_meta");

        List<Object[]> batch = new ArrayList<>();
        for (Task t : m.tasks()) {
            batch.add(new Object[]{
                    t.seq(), t.no(), t.dep(), t.name(), t.path(), t.big(), t.mid(), t.small(),
                    t.pStart(), t.pEnd(), t.owner(), t.part(), t.pProg(),
                    t.aStart(), t.aEnd(), t.aProg(), t.weight(), t.note(),
                    t.week(), t.startWeek(), t.endWeek(), t.isLeaf(), t.status()});
        }
        jdbc.batchUpdate("""
                INSERT INTO wbs_task
                  (seq, no, dep, name, path, big, mid, small,
                   p_start, p_end, owner, part, p_prog,
                   a_start, a_end, a_prog, weight, note,
                   week, start_week, end_week, is_leaf, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, batch);

        String src = file == null ? source.file().getName() : file.getName();
        // 부속 시트도 같은 파일에서 읽는다 — 업로드 파일과 설정 원본이 섞이지 않게 한다
        SheetTableReader.Table issueTable = (file == null)
                ? tables.read("이슈페이지", "이슈", "이슈이력관리")
                : tables.read(file, "이슈페이지", "이슈", "이슈이력관리");
        SheetTableReader.Table staffTable = (file == null)
                ? tables.read("투입인력현황")
                : tables.read(file, "투입인력현황");
        int issues = importTable(CoreDatasets.ISSUES, "이슈사항", issueTable, src);
        int staffing = importTable(CoreDatasets.STAFFING, "투입인력현황", staffTable, src);

        Map<String, String> meta = new LinkedHashMap<>();
        meta.put("project_name", m.projectName());
        meta.put("base", m.base());
        meta.put("max_week", String.valueOf(m.maxWeek()));
        meta.put("as_of", m.asOf());
        meta.put("summary_p_prog", String.valueOf(m.summary().pProg()));
        meta.put("summary_a_prog", String.valueOf(m.summary().aProg()));
        meta.put("summary_spi", String.valueOf(m.summary().spi()));
        meta.put("source_file", file == null ? source.file().getName() : file.getName());
        meta.put("imported_at", LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
        meta.forEach((k, v) -> jdbc.update("INSERT INTO wbs_meta (meta_key, meta_value) VALUES (?,?)", k, v));

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("ok", true);
        result.put("sourceFile", file == null ? source.file().getPath() : file.getPath());
        result.put("tasks", m.tasks().size());
        result.put("issueRows", issues);
        result.put("staffingRows", staffing);
        result.put("importedAt", meta.get("imported_at"));
        return result;
    }

    /**
     * 부속 시트(이슈·투입인력)를 데이터셋으로 저장한다.
     * 컬럼이 무엇이든 스키마 변경이 필요 없고, '데이터셋' 화면에서도 그대로 보인다 —
     * 저장 모델을 하나로 둔 이유다.
     */
    private int importTable(String datasetId, String name, SheetTableReader.Table t, String sourceFile) {
        if (!t.found()) return 0;
        return datasets.write(datasetId, name, name, sourceFile, null, t.headers(), t.rows());
    }

    public String sourceDescription() {
        return props.getFile();
    }
}
