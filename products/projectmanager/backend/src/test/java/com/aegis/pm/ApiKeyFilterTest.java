package com.aegis.pm;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import com.aegis.pm.config.ApiKeyFilter;

import jakarta.servlet.ServletException;

/**
 * 쓰기 API 키 필터 — 막아야 할 것만 막고, 나머지는 건드리지 않는가.
 *
 * <p>Spring 컨텍스트 없이 필터만 직접 돌린다. 이 필터의 계약은 단순해서
 * 통합 테스트가 필요하지 않고, 대신 <b>모든 분기</b>를 빠짐없이 본다 —
 * 키 미설정(비활성)·설정(활성)·읽기·preflight·잘못된 키.
 */
class ApiKeyFilterTest {

    private static final String KEY = "test-key-1234";

    // ── 키 미설정 = 비활성 (평식 판단 2026-09-18) ───────────────────────────

    @Test
    void 키가_없으면_검사하지_않는다() throws Exception {
        ApiKeyFilter f = new ApiKeyFilter("");
        assertEquals(200, run(f, "POST", "/api/datasets/x", null),
                "로컬 개발이 지금처럼 그대로 돌아가야 한다 — 그게 이 기본값의 이유다");
        assertEquals(200, run(f, "DELETE", "/api/admin/import", null));
    }

    @Test
    void 공백만_있는_키도_미설정으로_본다() throws Exception {
        assertEquals(200, run(new ApiKeyFilter("   "), "POST", "/api/uploads", null),
                "설정한 줄 알았는데 공백뿐이면 활성으로 오인하지 않는다");
    }

    // ── 키 설정 = 활성 ──────────────────────────────────────────────────────

    @Test
    void 키가_맞으면_통과한다() throws Exception {
        assertEquals(200, run(new ApiKeyFilter(KEY), "POST", "/api/dds/vocab", KEY));
    }

    @Test
    void 키가_없거나_틀리면_401이다() throws Exception {
        ApiKeyFilter f = new ApiKeyFilter(KEY);
        assertEquals(401, run(f, "POST", "/api/admin/import", null), "전량 교체는 반드시 막힌다");
        assertEquals(401, run(f, "POST", "/api/admin/import", "wrong"));
        assertEquals(401, run(f, "DELETE", "/api/datasets/DS-1", null), "삭제도 막힌다");
        assertEquals(401, run(f, "PUT", "/api/dds/bind/DS-1", null));
    }

    @Test
    void 막을_때_이유를_알려준다() throws Exception {
        MockHttpServletResponse res = call(new ApiKeyFilter(KEY), "POST", "/api/uploads", null);
        assertEquals(401, res.getStatus());
        String body = res.getContentAsString();
        assertTrue(body.contains("X-API-Key"), "무엇이 필요한지 말해야 부르는 쪽이 고칠 수 있다");
        assertTrue(!body.contains(KEY), "키 값 자체는 절대 응답에 넣지 않는다");
    }

    // ── 막지 않는 것 ────────────────────────────────────────────────────────

    @Test
    void 읽기는_막지_않는다() throws Exception {
        ApiKeyFilter f = new ApiKeyFilter(KEY);
        assertEquals(200, run(f, "GET", "/api/datasets", null),
                "조회까지 막으면 사용이 불편해지고, 그 불편이 키를 공유하게 만든다");
    }

    @Test
    void preflight는_막지_않는다() throws Exception {
        assertEquals(200, run(new ApiKeyFilter(KEY), "OPTIONS", "/api/datasets", null),
                "브라우저는 preflight 에 커스텀 헤더를 붙이지 않는다 — 여기서 막으면 정상 요청까지 실패한다");
    }

    @Test
    void api_밖_경로는_건드리지_않는다() throws Exception {
        assertEquals(200, run(new ApiKeyFilter(KEY), "POST", "/actuator/refresh", null),
                "이 필터의 대상은 /api/ 뿐이다");
    }

    // ── 보조 ────────────────────────────────────────────────────────────────

    private static int run(ApiKeyFilter f, String method, String uri, String key) throws Exception {
        return call(f, method, uri, key).getStatus();
    }

    private static MockHttpServletResponse call(ApiKeyFilter f, String method, String uri, String key)
            throws ServletException, IOException {
        MockHttpServletRequest req = new MockHttpServletRequest(method, uri);
        if (key != null) req.addHeader(ApiKeyFilter.HEADER, key);
        MockHttpServletResponse res = new MockHttpServletResponse();
        f.doFilter(req, res, new MockFilterChain());
        return res;
    }
}
