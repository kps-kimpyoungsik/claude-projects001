package com.aegis.pm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Constructor;
import java.util.function.BooleanSupplier;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import com.aegis.pm.config.MemoryGuardFilter;

/**
 * 메모리 압박 가드 — OOM 전에 거절하고, 평시엔 아무것도 건드리지 않는가.
 *
 * <p>힙을 실제로 채워 테스트하면 CI 가 죽거나 머신에 따라 결과가 달라진다. 그래서 압박 판정만
 * 주입하고(패키지 전용 생성자) <b>거절 계약</b>을 고정한다 — 상태코드·Retry-After·메시지·통과 경로.
 */
class MemoryGuardFilterTest {

    /** 압박 상태를 직접 주입한다 — 패키지 전용 생성자라 리플렉션으로 연다 */
    private static MemoryGuardFilter filter(boolean pressured) throws Exception {
        Constructor<MemoryGuardFilter> c =
                MemoryGuardFilter.class.getDeclaredConstructor(BooleanSupplier.class, int.class);
        c.setAccessible(true);
        return c.newInstance((BooleanSupplier) () -> pressured, 20);
    }

    // ── 평시: 아무것도 막지 않는다 ────────────────────────────────────────

    @Test
    void 압박이_없으면_그대로_통과시킨다() throws Exception {
        assertEquals(200, run(filter(false), "POST", "/api/uploads"),
                "가드가 본업을 방해하면 안 된다 — 평시 비용은 플래그 읽기 하나뿐이다");
    }

    @Test
    void 임계_판정_불가면_비활성이다() {
        // ratio 를 범위 밖으로 주면 fail-open (가드가 잘못 켜져 전부 막는 사고 방지)
        assertFalse(new MemoryGuardFilter(1.5, 20).enabled());
        assertFalse(new MemoryGuardFilter(0, 20).enabled());
    }

    // ── 압박: OOM 대신 503 ────────────────────────────────────────────────

    @Test
    void 압박이면_503과_안내문을_돌려준다() throws Exception {
        MockHttpServletResponse res = call(filter(true), "POST", "/api/uploads");
        assertEquals(503, res.getStatus(), "OOM 으로 죽는 대신 거절한다");
        assertEquals("20", res.getHeader("Retry-After"),
                "언제 다시 오면 되는지 알려준다 — 클라이언트가 즉시 재시도하면 압박이 더 커진다");
        String body = res.getContentAsString();
        assertTrue(body.contains("시스템에 부하가 있어 잠시 이후 요청 주시기 바랍니다."), body);
        assertTrue(body.contains("\"ok\":false"), "기존 오류 응답 규약과 같은 모양이어야 한다: " + body);
    }

    @Test
    void 압박이어도_상태조회는_막지_않는다() throws Exception {
        assertEquals(200, run(filter(true), "GET", "/api/meta"),
                "문지기가 진단 경로까지 막으면 무슨 일인지 확인할 방법이 사라진다");
    }

    @Test
    void 압박이어도_api가_아니면_막지_않는다() throws Exception {
        assertEquals(200, run(filter(true), "GET", "/index.html"));
    }

    @Test
    void 압박이어도_preflight는_통과시킨다() throws Exception {
        assertEquals(200, run(filter(true), "OPTIONS", "/api/uploads"),
                "preflight 를 막으면 정상 요청까지 실패한다");
    }

    // ── helper ────────────────────────────────────────────────────────────

    private static int run(MemoryGuardFilter f, String method, String uri) throws Exception {
        return call(f, method, uri).getStatus();
    }

    private static MockHttpServletResponse call(MemoryGuardFilter f, String method, String uri)
            throws Exception {
        MockHttpServletRequest req = new MockHttpServletRequest(method, uri);
        req.setRequestURI(uri);
        MockHttpServletResponse res = new MockHttpServletResponse();
        f.doFilter(req, res, new MockFilterChain());
        return res;
    }
}
