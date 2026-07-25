"""search_fn 어댑터 계층 — AEGIS 실시간 검색 연동 경계 (설계: plans/_plan/06_AGENT_DISPATCH_REPORTING.md §3-5).

## 실측 결과 (2026-07-19, 이번 세션 — T59 CFD 실측 우선, 추측 금지)

1. `search_all`은 aegis-mcp-go(Go, stdio MCP 서버)의 harness 검색 엔진을 쓴다.
   `D:\\aegis\\services\\aegis-mcp-go\\internal\\controller\\mcp_handler.go:2444`
   `handleSearchAll()` → `h.harness.Search(ctx, ...)`. stdio MCP 도구이므로 이 프로젝트의
   순수 Python 프로세스(subprocess/일반 런타임)에서 직접 import/호출할 수 없다 — 이는
   LLM 세션 툴 콜이지 프로세스 API가 아니다(설계서 §3-2 절대 금지 그대로).

2. graphify-hub는 포트 8000에 **실제로 살아있는** HTTP `/search`(GET·POST)·`/mentions`
   엔드포인트를 노출한다 — `D:\\aegis\\graphify-hub\\api_v1.py:143`(`search_get`),
   `:225`(`search`, POST), `:159`(`mentions`). `KH-2026-0682`(연결 표면 맵)에도
   "② HTTP API — graphify-hub 8000, /health 200, 통합 검색 /search"로 등재돼 있다.
   라이브 확인(`GET http://127.0.0.1:8000/health` → `{"status":"ok",...}` 200) 완료.

3. **그러나 다른 백엔드 엔진이다.** graphify-hub의 `/search`는 `Hub.asearch()`
   (반환 스키마: `task_intent`/`local_governance`/`retrieved_knowledge`/`sources`)를 쓰고,
   `search_all`이 쓰는 aegis-mcp-go의 `harness.Search()`와는 별개 인덱스·별개 저장소다.
   실측 질의로 직접 확인했다(추측 아님):
   ```
   POST /search {"query": "보안 취약점 점검 감사"}
     → {"sources": [], "retrieved_knowledge": {"skills_and_tools": []}, ...}  # 전부 빈 배열
   GET /mentions?q=aegis-security
     → {"items": [], "next_cursor": null, "has_more": false}  # 빈 배열
   ```
   즉 `resolve_agent_for_domain()`이 요구하는 `type=="command"` +
   `05_commands/slash/aegis-*.md` 경로의 슬래시 커맨드 파일이 이 hub의 FTS 인덱스에
   전혀 잡혀 있지 않다 — 라이브 엔드포인트가 있어도 필요한 데이터를 반환하지 못함을
   실측으로 확인했다.

## 결론

**실시간 조회 어댑터는 아직 구현 불가 — 이유: graphify-hub HTTP 엔드포인트(포트 8000)는
존재·가동 중이나, search_all이 참조하는 05_commands/slash/aegis-*.md 슬래시 커맨드
인덱스를 갖고 있지 않음(POST /search, GET /mentions 둘 다 실측상 빈 응답 확인).**
search_all과 동등한 결과를 내는 HTTP 경로는 이번 세션 기준 찾지 못했다.

그래서 이번 범위에서는 `StaticFallbackAdapter`만 제공한다 —
`agent_dispatch_resolver._FALLBACK_DEFAULT`를 대체하는 별도 매핑표를 새로 만들지 않고,
**항상 빈 결과를 반환**해 `resolve_agent_for_domain()` 자체가 이미 갖고 있는 내장 폴백
분기(`source="fallback_default"`)로 정직하게 위임한다. 만약 이 어댑터가 대신 합성 결과를
만들어 돌려주면 `source="search_all"`처럼 보여 "실시간 조회에 성공한 것"처럼 위장하게
되므로(T98 AIP 정직성 원칙 위반) 그렇게 하지 않는다.
"""

from __future__ import annotations

from typing import Callable


class StaticFallbackAdapter:
    """search_fn 포트 구현체 — 실시간 AEGIS 검색이 아직 없을 때 쓰는 최후 안전망.

    호출 시 항상 빈 리스트를 반환한다. 이렇게 하면
    `agent_dispatch_resolver.resolve_agent_for_domain()`이 `candidates == []` 분기를 타서
    자체 보유한 `_FALLBACK_DEFAULT` 매핑으로 `source="fallback_default"`를 정직하게
    표시한다 — 이 어댑터가 실시간 조회에 성공한 것처럼 위장하는 합성 결과를 만들지
    않는다.
    """

    def __call__(self, query: str | None) -> list[dict]:
        return []


def build_search_fn() -> Callable[[str], list[dict]]:
    """`resolve_agent_for_domain(search_fn=...)`에 바로 넘길 수 있는 현재 유일한 어댑터.

    실시간 HTTP 어댑터(예: `HttpSearchAllAdapter`)는 위 모듈 docstring에 적은 실측
    사유로 이번 세션에서는 구현하지 않았다 — 이후 aegis-mcp-go가 HTTP 게이트웨이를
    노출하거나 graphify-hub 인덱스에 슬래시 커맨드가 추가되면, 이 함수의 반환값만
    바꾸면 된다(포트-어댑터 경계, 설계서 §3-2 정신 그대로 — 호출부는 변경 불필요).
    """
    return StaticFallbackAdapter()
