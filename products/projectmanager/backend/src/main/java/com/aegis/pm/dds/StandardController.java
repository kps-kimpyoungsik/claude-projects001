package com.aegis.pm.dds;

import com.aegis.pm.common.Rows;
import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 표준 데이터셋 뼈대 + 바인딩 API (DDS Phase 2).
 *
 * 표준 삭제 엔드포인트는 없다 — 지우면 과거 데이터셋의 바인딩이 고아가 된다(04 ADR S6).
 * 내리려면 status 를 deprecated 로 바꾼다.
 */
@RestController
@RequestMapping("/api/dds")
public class StandardController {

    private final JdbcTemplate jdbc;
    private final StandardSeeder seeder;
    private final BindingEngine binding;
    private final DomainBuilder domains;
    private final CoreView views;

    public StandardController(JdbcTemplate jdbc, StandardSeeder seeder,
                              BindingEngine binding, DomainBuilder domains, CoreView views) {
        this.jdbc = jdbc;
        this.seeder = seeder;
        this.binding = binding;
        this.domains = domains;
        this.views = views;
    }

    @GetMapping("/standards")
    public List<Map<String, Object>> standards() {
        return Rows.lower(jdbc.queryForList("SELECT * FROM standard_dataset ORDER BY level, std_id"));
    }

    @GetMapping("/standards/{stdId}")
    public Map<String, Object> standard(@PathVariable String stdId) {
        Map<String, Object> out = new java.util.LinkedHashMap<>(
                Rows.lower(jdbc.queryForMap("SELECT * FROM standard_dataset WHERE std_id = ?", stdId)));
        // DOM 이면 부모 상속분까지 합쳐 돌려준다 — 복제가 아니라 조회 시 합치는 구조다
        out.put("fields", domains.fieldsOf(stdId));
        out.put("relations", Rows.lower(jdbc.queryForList(
                "SELECT * FROM standard_relation WHERE std_from = ? OR std_to = ?", stdId, stdId)));
        out.put("datasets", Rows.lower(jdbc.queryForList(
                "SELECT dataset_id, name, bind_ratio, ds_level FROM dataset WHERE std_id = ?", stdId)));
        return out;
    }

    @GetMapping("/standards/relations")
    public List<Map<String, Object>> relations() {
        return Rows.lower(jdbc.queryForList("SELECT * FROM standard_relation ORDER BY std_from, field_from"));
    }

    /** 실측 3테이블에서 표준 5종을 세운다. 초기 5종은 부트스트랩이라 승인 절차를 거치지 않는다 */
    @PostMapping("/standards/seed")
    public Map<String, Object> seedStandards() {
        return seeder.seed();
    }

    /**
     * 정형 테이블(`wbs_task`·`ia_screen`·`defect`)을 데이터셋으로 노출한다.
     * 행은 복사하지 않는다 — 원본에서 읽으므로 같은 사실이 두 벌이 되지 않는다.
     */
    @PostMapping("/views/register")
    public Map<String, Object> registerViews() {
        return views.register();
    }

    // ── 도메인 데이터셋 ─────────────────────────────────────────────────

    @GetMapping("/domains")
    public List<Map<String, Object>> domains() {
        return domains.domains();
    }

    /**
     * 미바인딩 컬럼을 확장 필드로 삼아 DOM 엔티티를 만든다.
     * 표준에 안 붙은 부분을 버리지 않고 그 도메인의 것으로 세우는 경로다.
     */
    @PostMapping("/domains")
    public Map<String, Object> createDomain(@RequestBody Map<String, String> body) {
        return domains.create(body.get("dataset_id"), body.get("domain"));
    }

    /**
     * 표준 승격 제안 — 같은 확장 필드를 여러 도메인이 쓰면 그건 도메인 고유가 아니다.
     * 제안만 한다: 승격하면 모든 하위가 상속받아 되돌리기가 비싸다.
     */
    @GetMapping("/domains/promotions")
    public List<Map<String, Object>> domainPromotions() {
        return domains.promotions();
    }

    // ── 바인딩 ──────────────────────────────────────────────────────────

    @PostMapping("/bind/{datasetId}")
    public Map<String, Object> bind(@PathVariable String datasetId) {
        return binding.bind(datasetId);
    }

    /** 전 데이터셋 일괄 바인딩 — 표준이 바뀐 뒤 다시 붙일 때 쓴다 */
    @PostMapping("/bind-all")
    public Map<String, Object> bindAll() {
        List<String> ids = jdbc.queryForList("SELECT dataset_id FROM dataset", String.class);
        List<Map<String, Object>> results = ids.stream().map(binding::bind).toList();
        long std = results.stream().filter(r -> "STD".equals(r.get("level"))).count();
        long dom = results.stream().filter(r -> "DOM".equals(r.get("level"))).count();
        return Map.of("total", ids.size(), "STD", std, "DOM", dom,
                      "USR", ids.size() - std - dom, "details", results);
    }

    @GetMapping("/bind/{datasetId}")
    public Map<String, Object> bindings(@PathVariable String datasetId) {
        return Map.of("bindings", binding.bindings(datasetId),
                      "unbound", binding.unbound(datasetId));
    }

    /** 사람이 바인딩을 고친다 — 고친 순간 학습되어 다음 데이터셋에도 적용된다 */
    @PutMapping("/bind/{datasetId}")
    public Map<String, Object> correct(@PathVariable String datasetId,
                                       @RequestBody Map<String, String> body) {
        return binding.correct(datasetId, body.get("col_name"),
                               body.get("std_id"), body.get("field_key"));
    }

    /**
     * 잘못 배운 것을 잊는다. 되돌리기 없는 학습은 학습이 아니라 각인이다 —
     * 사람 교정이 자동 판정을 덮으므로, 틀린 교정은 스스로 풀리지 않는다.
     */
    @DeleteMapping("/learned/{colNorm}")
    public Map<String, Object> unlearn(@PathVariable String colNorm,
                                       @RequestParam(required = false) String stdId,
                                       @RequestParam(required = false) String fieldKey) {
        int n = binding.unlearn(colNorm, stdId, fieldKey);
        return Map.of("col_norm", colNorm, "removed", n,
                      "note", n > 0 ? "학습을 지웠다. 다음 바인딩부터 규칙·통계로 다시 판정한다"
                                    : "지울 학습 기록이 없다");
    }

    /** 학습 현황 — 무엇을 얼마나 배웠는가 */
    @GetMapping("/learned")
    public List<Map<String, Object>> learned() {
        return binding.learned();
    }
}
