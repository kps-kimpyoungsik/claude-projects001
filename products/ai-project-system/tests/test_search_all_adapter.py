"""search_all_adapter — StaticFallbackAdapter가 항상 빈 결과를 반환하고, 그 결과
resolve_agent_for_domain의 내장 폴백(source="fallback_default")으로 정직하게 위임되는지 검증.

실측(2026-07-19): graphify-hub HTTP `/search`·`/mentions`(포트 8000, 라이브 확인)는
search_all이 참조하는 05_commands/slash/aegis-*.md 인덱스를 갖고 있지 않음(실측 빈 응답) —
그래서 이번 세션에는 실시간 HTTP 어댑터를 만들지 않았고, 이 테스트는 그 결정에 따른
StaticFallbackAdapter만 검증한다.
"""

from backend.adapters.aegis_bridge.search_all_adapter import (
    StaticFallbackAdapter,
    build_search_fn,
)
from backend.application.services.agent_dispatch_resolver import (
    DOMAIN_QUERY_HINT,
    resolve_agent_for_domain,
)
from backend.domain.requirements.codes import DOMAIN_CODES


def test_static_fallback_adapter_always_returns_empty_list():
    adapter = StaticFallbackAdapter()
    for query in [None, "", "그리드 부하분산 이중화 인프라", "존재하지 않는 질의"]:
        assert adapter(query) == []


def test_build_search_fn_returns_callable_matching_search_fn_port():
    search_fn = build_search_fn()
    assert callable(search_fn)
    assert search_fn(DOMAIN_QUERY_HINT["SEC"]) == []


def test_static_fallback_adapter_delegates_to_resolver_builtin_fallback():
    """search_fn이 빈 결과만 주면 resolve_agent_for_domain이 자체 _FALLBACK_DEFAULT로
    source="fallback_default"를 정직하게 표시해야 한다(합성 search_all 결과 위장 금지)."""
    search_fn = build_search_fn()

    for domain_code in DOMAIN_CODES:
        resolution = resolve_agent_for_domain(domain_code, search_fn=search_fn)
        assert resolution.source == "fallback_default"
        assert resolution.score is None


def test_static_fallback_adapter_result_matches_known_fallback_command():
    search_fn = build_search_fn()
    resolution = resolve_agent_for_domain("SEC", search_fn=search_fn)
    assert resolution.agent_command == "/aegis-security"
