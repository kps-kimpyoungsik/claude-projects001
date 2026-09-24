package com.aegis.pm.config;

import java.io.IOException;
import java.util.Set;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * 쓰기 요청에 API Key 를 요구한다 — 사내 단일 도구에 맞춘 최소 방어 (TODO P0 #3).
 *
 * <h3>왜 필터 하나인가</h3>
 * Spring Security 전면 도입은 이 규모에 과하다고 이미 판정했다(TODO "안 하는 게 낫다고 본 것").
 * 막아야 하는 것은 <b>인가된 사용자 구분</b>이 아니라 <b>외부에서 아무나 쓰는 것</b>이고,
 * 그건 헤더 하나로 충분하다.
 *
 * <h3>무엇을 막는가</h3>
 * POST·PUT·DELETE 전부. 실측 28개 엔드포인트 중에는 <b>전량 교체 2개</b>
 * (`/api/admin/import`·`/api/unittest/import`)와 <b>삭제 5개</b>가 있다 — 한 번의 호출로
 * 되돌리기 어려운 것들이다. 읽기(GET)는 막지 않는다: 사내망 조회까지 막으면 쓰기가 아니라
 * 사용이 불편해지고, 그 불편이 키를 공유하게 만든다.
 *
 * <h3>키가 없으면 비활성 — 의도된 선택</h3>
 * `pm.api-key` 가 비어 있으면 <b>검사하지 않는다</b>(평식 판단 2026-09-18). 로컬 개발·테스트가
 * 지금처럼 그대로 돌아가는 값이 크기 때문이다. 대신 <b>배포 시 키 설정을 빠뜨리면 무방비로
 * 뜬다</b> — 그래서 기동 로그에 상태를 한 줄 남긴다(조용히 비활성되지 않게).
 *
 * <p>CORS preflight(OPTIONS)는 통과시킨다. 브라우저는 preflight 에 커스텀 헤더를 붙이지 않으므로
 * 여기서 막으면 정상 요청까지 실패한다.
 */
@Component
public class ApiKeyFilter extends OncePerRequestFilter {

    public static final String HEADER = "X-API-Key";

    /** 검사 대상 메서드 — 읽기는 막지 않는다 */
    private static final Set<String> WRITE = Set.of("POST", "PUT", "DELETE", "PATCH");

    private final String apiKey;

    public ApiKeyFilter(@Value("${pm.api-key:}") String apiKey) {
        this.apiKey = apiKey == null ? "" : apiKey.trim();
    }

    /** 활성 여부 — 테스트·진단이 상태를 물을 수 있게 공개한다 */
    public boolean enabled() {
        return !apiKey.isEmpty();
    }

    @Override
    protected void initFilterBean() {
        logger.info(enabled()
                ? "[보안] 쓰기 API 키 검사 활성 (헤더 " + HEADER + ")"
                : "[보안] 쓰기 API 키 **미설정** — 검사하지 않습니다. 배포 환경이라면 pm.api-key 를 설정하세요");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {
        if (!enabled() || !WRITE.contains(req.getMethod())
                || !req.getRequestURI().startsWith("/api/")) {
            chain.doFilter(req, res);
            return;
        }
        if (apiKey.equals(req.getHeader(HEADER))) {
            chain.doFilter(req, res);
            return;
        }
        // 왜 막혔는지 알 수 있게 쓴다 — 키 값은 절대 남기지 않는다
        res.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        res.setContentType("application/json;charset=UTF-8");
        res.getWriter().write("{\"ok\":false,\"error\":\"쓰기 요청에는 "
                + HEADER + " 헤더가 필요합니다\"}");
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest req) {
        // preflight 에는 커스텀 헤더가 붙지 않는다 — 여기서 막으면 정상 요청까지 실패한다
        return "OPTIONS".equals(req.getMethod());
    }
}
