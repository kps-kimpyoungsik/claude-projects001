package com.aegis.pm.unittest;

import java.io.File;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.aegis.pm.config.UnitTestProperties;
import com.aegis.pm.excel.Cells;
import com.aegis.pm.excel.Workbooks;

/**
 * 단위테스트 영역 적재 — **참고하는 시트만** DB로 올린다.
 *   PC_IA(화면목록)              → ia_screen
 *   기획요청-결함혹은수정요청분   → defect
 *
 * 적재 이후 조회·수정은 전부 DB에서 이뤄지고 엑셀은 다시 읽지 않는다.
 * IA는 전량 교체(행 순서가 곧 화면 순서), 결함은 결함ID 기준 upsert(사람이 DB에서 고친 값 보존).
 */
@Service
public class IaImportService {

    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final UnitTestProperties props;
    private final JdbcTemplate jdbc;
    private final com.aegis.pm.pii.PiiVault pii;

    public IaImportService(UnitTestProperties props, JdbcTemplate jdbc, com.aegis.pm.pii.PiiVault pii) {
        this.props = props;
        this.jdbc = jdbc;
        this.pii = pii;
    }

    @Transactional
    public Map<String, Object> importAll() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ok", true);
        out.put("iaRows", importIa());
        out.put("defectRows", importDefects());
        out.put("importedAt", LocalDateTime.now().format(TS));
        return out;
    }

    /** PC_IA(화면목록) → ia_screen (전량 교체) */
    public int importIa() {
        return importIa(Workbooks.resolve(new File(props.getIaFile()).getAbsoluteFile()));
    }

    public int importIa(File f) {
        Object[][] g = Workbooks.grid(f, props.getIaSheet(), "PC_IA(화면목록)");
        if (g == null) throw new IllegalStateException("IA 시트를 찾을 수 없습니다: " + props.getIaSheet());

        // 헤더 행 탐색 (표지·타이틀 행이 위에 있을 수 있음) — 원본 getIaScopeJson 규칙 그대로
        int hr = -1;
        for (int r = 0; r < Math.min(g.length, 20); r++) {
            for (Object c : g[r]) {
                if (Pattern.compile("screen\\s*id", Pattern.CASE_INSENSITIVE).matcher(Cells.str(c)).find()) { hr = r; break; }
            }
            if (hr >= 0) break;
        }
        if (hr < 0) throw new IllegalStateException("IA 헤더행(Screen ID)을 찾지 못했습니다");

        List<String> head = new ArrayList<>();
        for (Object c : g[hr]) head.add(Cells.str(c));

        int cId = find(head, "screen\\s*id", 0);
        int cD1 = find(head, "^1\\s*depth", 0), cD2 = find(head, "^2\\s*depth", 0), cD3 = find(head, "^3\\s*depth", 0);
        int cD4 = find(head, "^4\\s*depth", 0), cD5 = find(head, "^5\\s*depth", 0);
        int cType = find(head, "^type$", 0);
        int cNote = find(head, "^비고", 0);
        int cOwner = find(head, "담당자", 0);
        int cStatus = find(head, "개발완료여부", 0);
        int cRemark = find(head, "작업설명", 0);
        if (cRemark < 0) cRemark = find(head, "^비고", cStatus + 1);
        int cPlan = find(head, "기획검토상태", 0);
        int cPnote = find(head, "검토내용", 0);

        jdbc.update("DELETE FROM ia_screen");
        String now = LocalDateTime.now().format(TS);
        List<Object[]> batch = new ArrayList<>();
        int seq = 0;
        for (int r = hr + 1; r < g.length; r++) {
            Object[] row = g[r];
            String sid = Cells.str(Cells.at(row, cId));
            String d1 = Cells.str(Cells.at(row, cD1));
            if (sid.isEmpty() || d1.isEmpty()) continue;
            batch.add(new Object[]{
                    seq++, sid, d1,
                    Cells.str(Cells.at(row, cD2)), Cells.str(Cells.at(row, cD3)),
                    Cells.str(Cells.at(row, cD4)), Cells.str(Cells.at(row, cD5)),
                    Cells.str(Cells.at(row, cType)), pii.scrub(Cells.str(Cells.at(row, cNote))),
                    pii.tokenize(com.aegis.pm.pii.PiiRegistry.PERSON, Cells.str(Cells.at(row, cOwner))), Cells.str(Cells.at(row, cStatus)),
                    pii.scrub(Cells.str(Cells.at(row, cRemark))), Cells.str(Cells.at(row, cPlan)),
                    pii.scrub(Cells.str(Cells.at(row, cPnote))), now});
        }
        jdbc.batchUpdate("""
                INSERT INTO ia_screen
                  (seq, screen_id, d1, d2, d3, d4, d5, scr_type, note, owner, status, remark, plan_status, plan_note, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, batch);
        return batch.size();
    }

    /** 기획요청-결함혹은수정요청분 → defect (결함ID 기준 upsert) */
    public int importDefects() {
        return (int) importDefects(Workbooks.resolve(new File(props.getDefectFile()).getAbsoluteFile()), null).get("rows");
    }

    /**
     * 결함 시트 적재 + 변경 요약.
     * 화면에서 등록한 건(manual)·IA 이벤트 건은 엑셀에 없어도 지우지 않는다 — kept 로 센다.
     */
    public Map<String, Object> importDefects(File f, String batchId) {
        Object[][] g = Workbooks.grid(f, props.getDefectSheet());
        if (g == null) throw new IllegalStateException("결함 시트를 찾을 수 없습니다: " + props.getDefectSheet());

        Map<String, Map<String, Object>> before = new LinkedHashMap<>();
        for (Map<String, Object> r : jdbc.queryForList(
                "SELECT defect_id, status, content, action, owner, severity, source FROM defect")) {
            before.put(String.valueOf(r.get("defect_id")), r);
        }

        int hr = props.getDefectHeaderRow() - 1;   // 1-based → 0-based
        String now = LocalDateTime.now().format(TS);
        List<String> addedIds = new ArrayList<>();
        List<String> updatedIds = new ArrayList<>();
        int unchanged = 0;
        int n = 0;
        for (int r = hr + 1; r < g.length; r++) {
            Object[] v = g[r];
            String id = Cells.str(Cells.at(v, 0));
            if (id.isEmpty()) continue;
            Map<String, Object> prev = before.get(id);
            if (prev == null) addedIds.add(id);
            else if (changed(prev, v)) updatedIds.add(id);
            else unchanged++;
            // 시트 컬럼 순서(원본 IAFB.C) 그대로: 결함ID·등록일·관련WBS·관련요구사항·시스템·모듈/화면·유형·심각도·
            //                                    우선순위·결함내용·재현절차·발견자·담당자·상태·조치내용·완료일·재테스트·비고
            upsert(id,
                    Cells.str(Cells.at(v, 1)), Cells.str(Cells.at(v, 2)), Cells.str(Cells.at(v, 3)),
                    Cells.str(Cells.at(v, 4)), Cells.str(Cells.at(v, 5)), Cells.str(Cells.at(v, 6)),
                    Cells.str(Cells.at(v, 7)), Cells.str(Cells.at(v, 8)), Cells.str(Cells.at(v, 9)),
                    Cells.str(Cells.at(v, 10)), Cells.str(Cells.at(v, 11)), Cells.str(Cells.at(v, 12)),
                    Cells.str(Cells.at(v, 13)), Cells.str(Cells.at(v, 14)), Cells.str(Cells.at(v, 15)),
                    Cells.str(Cells.at(v, 16)), Cells.str(Cells.at(v, 17)),
                    "excel", batchId, now);
            n++;
        }

        long kept = before.values().stream()
                .filter(x -> !"excel".equals(String.valueOf(x.get("source"))))
                .count();

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("rows", n);
        out.put("added", addedIds.size());
        out.put("updated", updatedIds.size());
        out.put("unchanged", unchanged);
        out.put("kept", (int) kept);
        out.put("addedIds", addedIds);
        out.put("updatedIds", updatedIds);
        return out;
    }

    /** 엑셀 값이 DB 값과 달라졌는지 — 사람이 화면에서 고친 것도 여기서 잡힌다 */
    private boolean changed(Map<String, Object> prev, Object[] v) {
        return !eq(prev.get("status"), Cells.str(Cells.at(v, 13)))
                || !eq(prev.get("content"), pii.scrub(Cells.str(Cells.at(v, 9))))
                || !eq(prev.get("action"), pii.scrub(Cells.str(Cells.at(v, 14))))
                || !eq(prev.get("owner"), pii.tokenOf(com.aegis.pm.pii.PiiRegistry.PERSON, Cells.str(Cells.at(v, 12))))
                || !eq(prev.get("severity"), Cells.str(Cells.at(v, 7)));
    }

    private static boolean eq(Object a, String b) {
        return (a == null ? "" : String.valueOf(a).trim()).equals(b == null ? "" : b.trim());
    }

    private void upsert(String id, String regDt, String wbsId, String reqId, String system, String screen,
                        String type, String sev, String prio, String content, String repro, String finder,
                        String owner, String status, String action, String doneDt, String retest, String remark,
                        String source, String batchId, String now) {
        finder = pii.tokenize(com.aegis.pm.pii.PiiRegistry.PERSON, finder);
        owner = pii.tokenize(com.aegis.pm.pii.PiiRegistry.PERSON, owner);
        content = pii.scrub(content);
        repro = pii.scrub(repro);
        action = pii.scrub(action);
        remark = pii.scrub(remark);
        String hash = DefectService.hashOf(remark);
        int updated = jdbc.update("""
                UPDATE defect SET reg_dt=?, wbs_id=?, req_id=?, system_name=?, screen=?, def_type=?, severity=?,
                                  priority=?, content=?, repro=?, finder=?, owner=?, status=?, action=?,
                                  done_dt=?, retest=?, remark=?, auto_hash=?, batch_id=?, updated_at=?
                 WHERE defect_id=?
                """, regDt, wbsId, reqId, system, screen, type, sev, prio, content, repro, finder, owner,
                status, action, doneDt, retest, remark, hash, batchId, now, id);
        if (updated == 0) {
            jdbc.update("""
                    INSERT INTO defect (defect_id, reg_dt, wbs_id, req_id, system_name, screen, def_type, severity,
                                        priority, content, repro, finder, owner, status, action, done_dt, retest,
                                        remark, auto_hash, source, batch_id, added_batch_id, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, id, regDt, wbsId, reqId, system, screen, type, sev, prio, content, repro, finder, owner,
                    status, action, doneDt, retest, remark, hash, source, batchId, batchId, now, now);
        }
    }

    private static int find(List<String> head, String regex, int from) {
        Pattern p = Pattern.compile(regex, Pattern.CASE_INSENSITIVE);
        for (int i = Math.max(0, from); i < head.size(); i++) {
            if (p.matcher(head.get(i)).find()) return i;
        }
        return -1;
    }
}
