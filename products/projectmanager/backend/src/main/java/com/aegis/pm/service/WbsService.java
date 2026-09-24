package com.aegis.pm.service;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Service;

import com.aegis.pm.domain.ProgressTree;
import com.aegis.pm.domain.Task;
import com.aegis.pm.domain.Tasks;
import com.aegis.pm.domain.WbsModel;
import com.aegis.pm.excel.Cells;
import com.aegis.pm.excel.SheetTableReader;
import com.aegis.pm.repo.WbsRepository;

/**
 * 화면이 쓰는 조회 서비스 — Apps Script의 getWbsDataJson / getWeeklyProgressJson / getIssuesJson 이관.
 *
 * 데이터 출처는 WbsRepository 포트 뒤에 있다 — 엑셀이든 DB든 이 클래스는 바뀌지 않는다.
 */
@Service
public class WbsService {

    /** 주차별 진척현황에서 대분류 대신 중분류로 펼칠 대상 (Apps Script WEEKLY_PROGRESS_EXPAND_BIGS_) */
    private static final List<String> EXPAND_BIGS = List.of("관리", "업무수행");

    private final WbsRepository repo;

    public WbsService(WbsRepository repo) {
        this.repo = repo;
    }

    /** 대시보드용 모델 (DASH_EXCLUDE 필터 적용 — getWbsDataJson 동일) */
    public WbsModel model() {
        WbsModel raw = repo.model();
        List<Task> kept = raw.tasks().stream().filter(Tasks::dashKeep).toList();
        return new WbsModel(raw.summary(), kept, raw.base(), raw.maxWeek(),
                raw.projectName(), raw.asOf(), raw.serverTime());
    }

    /** 필터 없는 전체 모델 (전체 일정 화면 등) */
    public WbsModel modelAll() {
        return repo.model();
    }

    public SheetTableReader.Table issues() {
        return repo.table("issues");
    }

    /** 원본 getIssuesJson() 형태 — 화면이 serverTime·todayDate 를 그대로 쓴다 */
    public Map<String, Object> issuesJson() {
        SheetTableReader.Table t = repo.table("issues");
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("found", t.found());
        out.put("headers", t.headers());
        out.put("rows", t.rows());
        out.put("serverTime", java.time.LocalDateTime.now()
                .format(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
        out.put("todayDate", LocalDate.now().format(Cells.YMD));
        return out;
    }

    /** 원본 setIssueStatus() — 저장소가 쓰기를 지원할 때만 반영된다 */
    public Map<String, Object> setIssueStatus(String no, boolean done) {
        return repo.updateIssueStatus(no, done);
    }

    public SheetTableReader.Table staffing() {
        return repo.table("staffing");
    }

    public Map<String, Object> meta() {
        WbsModel m = repo.model();
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("source", repo.describe());
        out.put("projectName", m.projectName());
        out.put("base", m.base());
        out.put("asOf", m.asOf());
        out.put("tasks", m.tasks().size());
        out.put("serverTime", m.serverTime());
        return out;
    }

    /** 주차별 진척현황 — getWeeklyProgressJson 이관 */
    public Map<String, Object> weeklyProgress() {
        ProgressTree tree = tree();
        LocalDate asOf = ProgressTree.effectiveAsOf();
        LocalDate curMon = ProgressTree.mondayOf(asOf);
        LocalDate curFri = curMon.plusDays(4);
        LocalDate nextMon = curMon.plusDays(7);
        LocalDate nextFri = nextMon.plusDays(4);

        List<Map<String, Object>> rows = new ArrayList<>();
        rows.add(row("전체", tree.projectRoot, asOf, nextFri));
        for (ProgressTree.Node big : tree.projectRoot.children) {
            if (EXPAND_BIGS.contains(big.name)) {
                for (ProgressTree.Node mid : big.children) {
                    rows.add(row(mid.name, mid, asOf, nextFri));
                }
            } else {
                rows.add(row(big.name, big, asOf, nextFri));
            }
        }

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("asOfDate", asOf.format(Cells.YMD));
        out.put("holidayShift", !asOf.equals(LocalDate.now()));
        out.put("curRange", Map.of("start", curMon.format(Cells.YMD), "end", curFri.format(Cells.YMD)));
        out.put("nextRange", Map.of("start", nextMon.format(Cells.YMD), "end", nextFri.format(Cells.YMD)));
        out.put("rows", rows);
        return out;
    }

    private ProgressTree tree() {
        WbsModel m = repo.model();
        return new ProgressTree(m.tasks(), m.base());
    }

    private Map<String, Object> row(String label, ProgressTree.Node node, LocalDate asOf, LocalDate nextFri) {
        double plan = ProgressTree.progressAsOf(node, asOf, "plan") * 100;
        double actual = ProgressTree.progressAsOf(node, asOf, "actual") * 100;
        double nextPlan = ProgressTree.progressAsOf(node, nextFri, "plan") * 100;
        double delay = (plan > 0 && plan > actual) ? (plan - actual) / plan * 100 : 0;
        double rate = plan > 0 ? Math.min(100, actual / plan * 100) : (actual > 0 ? 100 : 0);

        Map<String, Object> r = new LinkedHashMap<>();
        r.put("category", label);
        r.put("curPlan", plan);
        r.put("curActual", actual);
        r.put("curRate", rate);
        r.put("curDelay", delay);
        r.put("nextPlan", nextPlan);
        return r;
    }

}
