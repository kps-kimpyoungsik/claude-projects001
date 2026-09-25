package com.aegis.pm.engine;

import java.util.List;
import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 범용 규칙 발견 엔진 API.
 *
 * <pre>
 *   GET  /api/engine/inventory        자료 리스트업 — 전 데이터셋 구조·역할·헤더 의심·정제 제안 요약
 *   GET  /api/engine/profile/{id}     컬럼별 특징·역할·근거 + 정제 계획
 *   POST /api/engine/refine/{id}      정제 적용 — 원본은 두고 {id}-R 새 데이터셋
 *   GET  /api/engine/traces/{id}      사라지거나 바뀐 값 이력 + 사람 결정
 *   POST /api/engine/restore/{id}     복원 {op, col?, row?} — 그 정제를 하지 않고 정제본 재생성
 *   POST /api/engine/unrestore/{id}   복원 취소
 *   PUT  /api/engine/edit/{id}        직접 수정 {row, col, value} — 원본 칸 수정 + EDIT 이력 + 정제본 재생성
 *   PUT  /api/engine/columns/{id}     컬럼 이름 바꾸기 {이전: 새 이름} — 참조·이력 함께 옮김 + COLUMN_RENAME 이력
 *   GET  /api/engine/groups           자동 분류된 묶음 (비슷한 양식끼리)
 *   POST /api/engine/reverify/{group} 묶음 재검증 — 묶음 전체 자료로 역할 재판단
 *   POST /api/engine/reingest/{id}?header=N  봉인 원본에서 헤더 행 지정 재적재 (N: 1부터, 0=헤더 없음, 생략=자동)
 * </pre>
 */
@RestController
@RequestMapping("/api/engine")
public class EngineController {

    private final EngineService engine;

    public EngineController(EngineService engine) {
        this.engine = engine;
    }

    @GetMapping("/inventory")
    public List<Map<String, Object>> inventory() {
        return engine.inventory();
    }

    @GetMapping("/profile/{id}")
    public Map<String, Object> profile(@PathVariable String id) {
        return engine.profile(id);
    }

    @PostMapping("/refine/{id}")
    public Map<String, Object> refine(@PathVariable String id) {
        return engine.apply(id);
    }

    @GetMapping("/traces/{id}")
    public Map<String, Object> traces(@PathVariable String id) {
        return engine.traces(id);
    }

    @PostMapping("/restore/{id}")
    public Map<String, Object> restore(@PathVariable String id, @RequestBody Map<String, Object> b) {
        return engine.restore(id, op(b), (String) b.get("col"), row(b));
    }

    @PostMapping("/unrestore/{id}")
    public Map<String, Object> unrestore(@PathVariable String id, @RequestBody Map<String, Object> b) {
        return engine.unrestore(id, op(b), (String) b.get("col"), row(b));
    }

    @PutMapping("/edit/{id}")
    public Map<String, Object> edit(@PathVariable String id, @RequestBody Map<String, Object> b) {
        if (!(b.get("row") instanceof Number) || !(b.get("col") instanceof String)) throw new IllegalArgumentException("row·col 필요");
        return engine.edit(id, ((Number) b.get("row")).intValue(), (String) b.get("col"), b.get("value") == null ? "" : String.valueOf(b.get("value")));
    }

    /** 컬럼 이름 바꾸기 {"이전 이름": "새 이름", …} — 헤더 없는 표(col1…)에 이름 붙이기 */
    @PutMapping("/columns/{id}")
    public Map<String, Object> rename(@PathVariable String id, @RequestBody Map<String, String> renames) {
        return engine.renameColumns(id, renames);
    }

    @GetMapping("/groups")
    public List<Map<String, Object>> groups() {
        return engine.groups();
    }

    @PostMapping("/reverify/{group}")
    public Map<String, Object> reverify(@PathVariable String group) {
        return engine.reverify(group);
    }

    /** header: 사람이 보는 시트 행 번호(1부터). 0 = 헤더 없음 */
    @PostMapping("/reingest/{id}")
    public Map<String, Object> reingest(@PathVariable String id, @RequestParam(required = false) Integer header) throws Exception {
        return engine.reingest(id, header == null ? null : header - 1);
    }

    private static final java.util.Set<String> OPS = java.util.Set.of("NORMALIZE_NULL", "TRIM_SPACE", "DATE_SERIAL_TO_ISO",
            "DATE_FORMAT_UNIFY", "NUMBER_UNFORMAT", "DEDUPE_ROWS", "DROP_EMPTY_COLUMN");

    private static String op(Map<String, Object> b) {
        Object o = b.get("op");
        if (!(o instanceof String s) || !OPS.contains(s)) throw new IllegalArgumentException("복원할 수 없는 op: " + o);
        return s;
    }

    private static int row(Map<String, Object> b) {
        return b.get("row") instanceof Number n ? n.intValue() : -1;
    }
}
