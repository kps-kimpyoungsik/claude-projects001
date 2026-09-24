package com.aegis.pm.repo;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Repository;

import com.aegis.pm.domain.Task;
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
    private final com.aegis.pm.pii.PiiVault pii;

    public ExcelWbsRepository(WbsExcelReader reader, SheetTableReader tables, com.aegis.pm.pii.PiiVault pii) {
        this.reader = reader;
        this.tables = tables;
        this.pii = pii;
    }

    /**
     * 엑셀을 직접 읽는 경로도 DB 경로와 똑같이 보호한다 — 안 그러면 기본 설정(source=excel)에서 원문이 응답으로 나간다
     * (실측 2026-09-24: DB 전환 후에도 /api/wbs 담당자 276건 평문). 엑셀 원본 파일 자체의 보호는 2단계(pii 설계서 §8).
     */
    @Override
    public WbsModel model() {
        WbsModel m = reader.read();
        String person = com.aegis.pm.pii.PiiRegistry.PERSON;
        // 요청마다 부른다 — 같은 값은 요청 안에서 한 번만 (276행 → 담당자 고유값 수십 개). 요청 단위라 금고와 어긋날 일이 없다
        java.util.Map<String, String> memo = new java.util.HashMap<>();
        java.util.function.Function<String, String> owner = v -> v == null ? null
                : memo.computeIfAbsent("o:" + v, k -> pii.tokenize(person, v));
        java.util.function.Function<String, String> text = v -> v == null ? null
                : memo.computeIfAbsent("t:" + v, k -> pii.scrub(v));
        m.tasks().forEach(t -> owner.apply(t.owner()));   // 먼저 금고에 올려야 작업명 속 이름도 찾는다
        java.util.List<Task> tasks = m.tasks().stream().map(t -> new Task(t.seq(), t.no(), t.dep(),
                text.apply(t.name()), text.apply(t.path()), text.apply(t.big()), text.apply(t.mid()), text.apply(t.small()),
                t.pStart(), t.pEnd(), owner.apply(t.owner()), t.part(), t.pProg(), t.aStart(), t.aEnd(),
                t.aProg(), t.weight(), text.apply(t.note()), t.week(), t.startWeek(), t.endWeek(), t.isLeaf(),
                t.status())).toList();
        return new WbsModel(m.summary(), tasks, m.base(), m.maxWeek(), m.projectName(), m.asOf(), m.serverTime());
    }

    @Override
    public Table table(String logical) {
        Table t = switch (logical) {
            case "issues" -> tables.read("이슈페이지", "이슈", "이슈이력관리");
            case "staffing" -> tables.read("투입인력현황");
            default -> new SheetTableReader.Table(false, java.util.List.of(), java.util.List.of());
        };
        java.util.List<java.util.Map<String, String>> rows = t.rows().stream().map(r -> {
            java.util.Map<String, String> c = new java.util.LinkedHashMap<>();
            r.forEach((h, v) -> {
                String k = com.aegis.pm.pii.PiiRegistry.kindOfHeader(h);
                c.put(h, k != null ? pii.tokenize(k, v) : pii.scrub(v));
            });
            return c;
        }).toList();
        return new Table(t.found(), t.headers(), rows);
    }

    @Override
    public String describe() {
        return "excel";
    }
}
