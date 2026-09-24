package com.aegis.pm.config;

import java.io.IOException;
import java.lang.management.ManagementFactory;
import java.lang.management.MemoryPoolMXBean;
import java.lang.management.MemoryType;
import java.util.Optional;
import java.util.function.BooleanSupplier;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * 메모리 압박이 임계를 넘으면 <b>OOM 이 나기 전에</b> 503 으로 정중히 거절한다.
 *
 * <h3>왜 필요한가</h3>
 * 힙을 고정값으로 정하기 어렵다 — 작으면 대용량 집계가 죽고, 크면 머신을 민다. 그래서 힙은
 * {@code -XX:MaxRAMPercentage} 로 머신에 맞춰 자라게 두고(start.cmd/start.sh), <b>한계에 닿기 전에
 * 요청을 거절</b>하는 문지기를 둔다. OOM 은 프로세스를 죽이지만 503 은 다음 요청을 살린다.
 *
 * <h3>어떻게 재는가 — "GC 이후"만 본다</h3>
 * {@code Runtime.freeMemory()} 로 재면 <b>아직 수거 안 된 쓰레기까지 사용량으로 세어</b> 멀쩡한
 * 서버를 막는다. 그래서 {@link MemoryPoolMXBean#setCollectionUsageThreshold} 를 쓴다 — 이 값은
 * <b>가장 최근 GC 직후</b>의 old 영역 사용량으로만 판정하므로, 임계를 넘었다면 "치워도 안 줄었다"
 * 는 뜻이다. 진짜 압박만 잡힌다.
 *
 * <p>플래그는 <b>스스로 풀린다</b> — 다음 GC 에서 사용량이 임계 아래로 내려가면 false 가 된다.
 * 별도 해제 로직도, 재기동도 필요 없다.
 *
 * <h3>무엇을 막고 무엇을 통과시키는가</h3>
 * {@code /api/**} 를 막되 {@code /api/meta} 는 통과시킨다 — 압박 중에도 상태는 볼 수 있어야
 * 한다. 문지기가 진단 경로까지 막으면 무슨 일인지 확인할 방법이 사라진다.
 *
 * <p>old 영역 풀을 못 찾거나 임계가 0 이하면 <b>비활성</b>(fail-open). 가드가 본업을 망가뜨리지
 * 않는다.
 */
@Component
public class MemoryGuardFilter extends OncePerRequestFilter {

    /** 압박 중에도 열어 두는 경로 — 진단은 막지 않는다 */
    private static final String HEALTH = "/api/meta";

    private final double ratio;
    private final int retryAfterSec;
    /** 압박 여부 판정 — 테스트가 갈아끼울 수 있게 seam 으로 둔다 */
    private final BooleanSupplier underPressure;
    private final String poolName;

    @Autowired   // 생성자가 둘이라 Spring 이 쓸 쪽을 명시한다(다른 하나는 테스트 전용)
    public MemoryGuardFilter(@Value("${pm.mem-guard.threshold:0.85}") double ratio,
                             @Value("${pm.mem-guard.retry-after-sec:20}") int retryAfterSec) {
        this.ratio = ratio;
        this.retryAfterSec = retryAfterSec;
        Optional<MemoryPoolMXBean> pool = oldGenPool();
        if (ratio <= 0 || ratio >= 1 || pool.isEmpty()) {
            this.underPressure = () -> false;      // fail-open
            this.poolName = null;
        } else {
            MemoryPoolMXBean p = pool.get();
            long max = p.getUsage().getMax();
            if (max <= 0) {                        // 상한을 모르면 비율 판정이 성립하지 않는다
                this.underPressure = () -> false;
                this.poolName = null;
            } else {
                p.setCollectionUsageThreshold((long) (max * ratio));
                this.underPressure = p::isCollectionUsageThresholdExceeded;
                this.poolName = p.getName();
            }
        }
    }

    /** 테스트 전용 — 압박 상태를 직접 주입한다(힙을 실제로 채우지 않고 동작을 고정하기 위해) */
    MemoryGuardFilter(BooleanSupplier underPressure, int retryAfterSec) {
        this.ratio = 0;
        this.retryAfterSec = retryAfterSec;
        this.underPressure = underPressure;
        this.poolName = "(test)";
    }

    /** GC 로 수거되지 않는 장기 생존 영역 — 여기가 차면 진짜 위험이다 */
    private static Optional<MemoryPoolMXBean> oldGenPool() {
        return ManagementFactory.getMemoryPoolMXBeans().stream()
                .filter(p -> p.getType() == MemoryType.HEAP)
                .filter(MemoryPoolMXBean::isCollectionUsageThresholdSupported)
                .filter(p -> p.getName().toLowerCase().contains("old")
                          || p.getName().toLowerCase().contains("tenured"))
                .findFirst();
    }

    public boolean enabled() {
        return poolName != null;
    }

    @Override
    protected void initFilterBean() {
        logger.info(enabled()
                ? "[메모리] 압박 가드 활성 — " + poolName + " 사용률 " + (int) (ratio * 100) + "% 초과 시 503"
                : "[메모리] 압박 가드 **비활성** — old 영역 풀 또는 힙 상한을 확인할 수 없습니다");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {
        if (!underPressure.getAsBoolean()) {
            chain.doFilter(req, res);
            return;
        }
        logger.warn("[메모리] 압박으로 요청 거절: " + req.getMethod() + " " + req.getRequestURI());
        res.setStatus(HttpServletResponse.SC_SERVICE_UNAVAILABLE);
        res.setHeader("Retry-After", String.valueOf(retryAfterSec));
        res.setContentType("application/json;charset=UTF-8");
        res.getWriter().write("{\"ok\":false,\"retryAfterSec\":" + retryAfterSec
                + ",\"error\":\"시스템에 부하가 있어 잠시 이후 요청 주시기 바랍니다.\"}");
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest req) {
        String uri = req.getRequestURI();
        return !uri.startsWith("/api/") || HEALTH.equals(uri) || "OPTIONS".equals(req.getMethod());
    }
}
