package com.aegis.pm.dds;

import java.util.LinkedHashMap;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * 적재 직후 자동 처리 — 바인딩 → 패싯 → 자격 평가 (02_구현계획서 3-8 · 4-5, 06 §5).
 *
 * <p><b>실패해도 적재는 성공한다.</b> 그래서 두 가지를 지킨다:
 * <ol>
 *   <li>적재 트랜잭션이 <b>커밋된 뒤</b> 실행한다 — 같은 트랜잭션 안에서 SQL 오류가 나면 예외를 잡아도
 *       트랜잭션이 rollback-only 가 돼 업로드 전체가 되돌아간다.</li>
 *   <li>단계마다 <b>별도 트랜잭션</b>(REQUIRES_NEW) — 한 단계 실패가 앞 단계 결과를 지우지 않는다.</li>
 * </ol>
 * {@code pm.dds.auto-pipeline=false} 로 끌 수 있다(수동: {@code POST /api/dds/bind-all} · {@code /qualify}).
 */
@Service
public class DatasetPipeline {

    private static final Logger log = LoggerFactory.getLogger(DatasetPipeline.class);

    private final BindingEngine binding;
    private final FacetService facets;
    private final QualificationService qualification;
    private final TransactionTemplate tx;
    private final boolean enabled;

    public DatasetPipeline(BindingEngine binding, FacetService facets, QualificationService qualification,
                           PlatformTransactionManager txm, @Value("${pm.dds.auto-pipeline:true}") boolean enabled) {
        this.binding = binding;
        this.facets = facets;
        this.qualification = qualification;
        this.tx = new TransactionTemplate(txm);
        this.tx.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
        this.enabled = enabled;
    }

    /** 적재 끝에 부른다 — 트랜잭션 중이면 커밋 뒤로 미룬다 */
    public void afterWrite(String datasetId) {
        if (!enabled) return;
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    run(datasetId);
                }
            });
        } else {
            run(datasetId);
        }
    }

    /** 단계별 결과 — 실패한 단계는 사유만 남기고 다음 단계로 간다 */
    public Map<String, Object> run(String datasetId) {
        Map<String, Object> out = new LinkedHashMap<>();
        step(out, "binding", () -> binding.bind(datasetId));
        step(out, "facets", () -> facets.classify(datasetId));
        step(out, "qualification", () -> qualification.evaluate(datasetId));
        return out;
    }

    private void step(Map<String, Object> out, String name, java.util.function.Supplier<Object> body) {
        try {
            out.put(name, tx.execute(s -> body.get()));
        } catch (RuntimeException e) {
            // 값은 로그에 남기지 않는다(pii 지침 G-10) — 단계명·예외 종류만
            log.warn("[DDS] 자동 처리 {} 실패 — 적재는 유지 ({})", name, e.getClass().getSimpleName());
            out.put(name, Map.of("error", e.getClass().getSimpleName()));
        }
    }
}
