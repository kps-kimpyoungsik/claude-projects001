package com.aegis.pm.dds;

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
 * 어휘 사전 API (DDS Phase 1).
 *
 * <p>삭제 엔드포인트는 없다 — 용어는 지우지 않고 {@code status=deprecated} 로 내린다(05 §4.2).
 * 지워 버리면 그 용어로 해석된 과거 데이터셋의 근거가 사라진다.
 */
@RestController
@RequestMapping("/api/dds/vocab")
public class VocabController {

    private final VocabStore store;
    private final VocabSeeder seeder;

    public VocabController(VocabStore store, VocabSeeder seeder) {
        this.store = store;
        this.seeder = seeder;
    }

    @GetMapping
    public List<Map<String, Object>> list(@RequestParam(required = false) String level,
                                          @RequestParam(required = false) String kind,
                                          @RequestParam(required = false) String q) {
        return store.terms(level, kind, q);
    }

    @GetMapping("/{termId}")
    public Map<String, Object> detail(@PathVariable String termId) {
        return store.term(termId);
    }

    @GetMapping("/{termId}/history")
    public List<Map<String, Object>> history(@PathVariable String termId) {
        return store.history(termId);
    }

    /** 컬럼명 하나를 사전으로 해석해 본다. 실패도 기록된다(진화 신호) */
    @GetMapping("/match")
    public Map<String, Object> match(@RequestParam String token) {
        Map<String, Object> hit = store.match(token);
        return hit == null ? Map.of("token", token, "matched", false) : hit;
    }

    /** 사전에 없어 실패한 토큰 목록 — 무엇을 더 채워야 하는지 */
    @GetMapping("/misses")
    public List<Map<String, Object>> misses(@RequestParam(defaultValue = "1") int minHits) {
        return store.misses(minHits);
    }

    /**
     * 공통(STD) 승격 제안 — 근거만 제시한다. 승격 자체는 사람이 PUT 으로 level 을 바꿔야 일어난다.
     * 시스템이 자동으로 올리지 않는 이유: 표준은 합의이고 빈도는 합의의 근거일 뿐이다(05 ADR V5).
     */
    @GetMapping("/promotions")
    public List<Map<String, Object>> promotions() {
        return store.promotions();
    }

    /**
     * 중복 후보 — 같은 원천을 가리키는 것으로 보이는 표기 묶음 (T115 SSI).
     * 시스템은 후보만 낸다. 합치는 것은 사람이 한다.
     */
    @GetMapping("/duplicates")
    public List<Map<String, Object>> duplicates() {
        return store.duplicates();
    }

    /** 흡수 출처 — scope_in/scope_out 으로 "무엇을 일부러 뺐는지"까지 읽는다 */
    @GetMapping("/sources")
    public List<Map<String, Object>> sources() {
        return store.sources();
    }

    @PostMapping
    public Map<String, Object> create(@RequestBody Map<String, Object> body) {
        String reason = String.valueOf(body.getOrDefault("reason", "사람 등록"));
        String id = store.save(body, "human", reason);
        return Map.of("term_id", id);
    }

    @PutMapping("/{termId}")
    public Map<String, Object> update(@PathVariable String termId, @RequestBody Map<String, Object> body) {
        body.put("term_id", termId);
        String reason = String.valueOf(body.getOrDefault("reason", "사람 수정"));
        return Map.of("term_id", store.save(body, "human", reason));
    }

    /** DB 실측에서 초기 사전을 채운다. 재실행해도 사람이 정한 용어는 덮이지 않는다 */
    @PostMapping("/seed")
    public Map<String, Object> seed() {
        return seeder.seedAll();
    }
}
