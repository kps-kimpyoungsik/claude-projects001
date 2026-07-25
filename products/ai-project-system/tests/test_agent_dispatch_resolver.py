"""agent_dispatch_resolver — mock search_fn으로 §3-1 실측 사례 재현(정상 매칭·0건 폴백·TTL 캐시)."""

from backend.application.services.agent_dispatch_resolver import (
    DOMAIN_QUERY_HINT,
    resolve_agent_for_domain,
)


def _mock_search_fn_with_match(query: str) -> list[dict]:
    return [
        {"type": "memory", "path": "some/knowhow/report.md", "score": 0.61},
        {
            "type": "command",
            "path": "D:/aegis/base/05_commands/slash/aegis-security.md",
            "score": 0.56,
        },
        {"type": "skill", "path": "skills/pptx-builder/SKILL.md", "score": 0.60},
    ]


def _mock_search_fn_no_match(query: str) -> list[dict]:
    return [
        {"type": "memory", "path": "some/knowhow/report.md", "score": 0.61},
        {"type": "skill", "path": "skills/pptx-builder/SKILL.md", "score": 0.60},
    ]


def test_all_domain_codes_have_query_hint():
    from backend.domain.requirements.codes import DOMAIN_CODES

    for code in DOMAIN_CODES:
        assert code in DOMAIN_QUERY_HINT


def test_resolve_agent_for_domain_finds_command_and_filters_noise():
    resolution = resolve_agent_for_domain("SEC", search_fn=_mock_search_fn_with_match)
    assert resolution.agent_command == "/aegis-security"
    assert resolution.source == "search_all"
    assert resolution.score == 0.56


def test_resolve_agent_for_domain_falls_back_when_zero_matches():
    resolution = resolve_agent_for_domain("SEC", search_fn=_mock_search_fn_no_match)
    assert resolution.source == "fallback_default"
    assert resolution.agent_command == "/aegis-security"  # _FALLBACK_DEFAULT 값


def test_resolve_agent_for_domain_uses_cache_within_ttl():
    calls = []

    def counting_search_fn(query):
        calls.append(query)
        return _mock_search_fn_with_match(query)

    cache = {}
    clock = {"now": 0.0}
    now_fn = lambda: clock["now"]

    first = resolve_agent_for_domain("SEC", search_fn=counting_search_fn, cache=cache, now_fn=now_fn)
    assert first.source == "search_all"
    assert len(calls) == 1

    clock["now"] = 60.0  # 1분 경과 — TTL(15분) 이내
    second = resolve_agent_for_domain("SEC", search_fn=counting_search_fn, cache=cache, now_fn=now_fn)
    assert second.source == "cache"
    assert len(calls) == 1  # search_fn 재호출 안 됨


def test_resolve_agent_for_domain_cache_expires_after_ttl():
    calls = []

    def counting_search_fn(query):
        calls.append(query)
        return _mock_search_fn_with_match(query)

    cache = {}
    clock = {"now": 0.0}
    now_fn = lambda: clock["now"]

    resolve_agent_for_domain("SEC", search_fn=counting_search_fn, cache=cache, now_fn=now_fn)
    assert len(calls) == 1

    clock["now"] = 15 * 60 + 1  # TTL(15분) 초과
    resolution = resolve_agent_for_domain("SEC", search_fn=counting_search_fn, cache=cache, now_fn=now_fn)
    assert resolution.source == "search_all"
    assert len(calls) == 2  # 캐시 만료로 재호출
