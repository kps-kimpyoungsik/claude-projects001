"""[Phase 3 Ext] 도메인코드 → AEGIS 전문가 agent 실시간 조회 (설계: plans/_plan/06_AGENT_DISPATCH_REPORTING.md §3).

정적 매핑표를 두지 않는다 — 사용자 명시 거부(§3, 2026-07-19): "aegis 시스템에서도 agents
역할 목록 검색 할수 있도록 실시간 동기화". `mcp__aegis__search_all`이 이 프로젝트가 아닌
Claude Code 세션 툴이라 이 모듈(순수 Python 런타임)에서 직접 import/호출할 수 없다(설계서
§3-2 지시, "MCP 도구를 Python 코드에서 직접 호출하려는 시도"는 절대 금지 사항) — 그래서
`search_fn: Callable[[str], list[dict]]`을 의존성 주입 파라미터로 받는 포트 패턴을 쓴다.
실제 AEGIS `search_all` 연동은 이 함수를 감싸는 어댑터가 이후 채운다(이번 범위 밖).

TTL 캐시는 실제 시간(datetime.now)에 의존하면 테스트가 15분을 기다려야 하므로, 현재 시각을
반환하는 `now_fn`(기본 time.monotonic)을 주입 가능하게 해 테스트에서 시간을 직접 흘려보낼
수 있게 한다.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

# §3-2 — §5 표의 "영역 설명" 한국어 그대로 사용(코드 문자열 단독 질의는 §3-1 실측상 명중률이
# 낮음 — "GRID"만 넣는 것보다 "그리드 부하분산 이중화 인프라"가 훨씬 잘 맞았다).
DOMAIN_QUERY_HINT = {
    "WEB": "프론트엔드 웹 UI 화면 설계 구현",
    "WAS": "애플리케이션 서버 백엔드 로직 구현",
    "DB": "데이터베이스 스키마 쿼리 구현",
    "SEC": "암호화 솔루션 SSL 보안",
    "GRID": "그리드 부하분산 이중화 인프라",
    "A11Y": "웹접근성 UI 디자인",
    "VULN": "소스코드 취약성 점검 보안 감사",
    "GW": "중계서버 게이트웨이 인프라",
    "LLM": "LLM 연계 python 개발 구현",
    "RPT": "보고서 산출물 비서 작성",
}

# §3-4 — AEGIS 조회가 실패(네트워크·MCP 미가용 등)했을 때만 쓰는 최후 안전망.
# 구버전 정적 매핑표와 다른 점: 정상 조회가 되는 한 절대 우선 참조되지 않는다(흐름 5번에서만 도달).
_FALLBACK_DEFAULT = {
    "WEB": "/aegis-design",
    "WAS": "/aegis-dev",
    "DB": "/aegis-dev",
    "SEC": "/aegis-security",
    "GRID": "/aegis-infra",
    "A11Y": "/aegis-design",
    "VULN": "/aegis-security",
    "GW": "/aegis-infra",
    "LLM": "/aegis-dev",
    "RPT": "/aegis-secretary",
}

_TTL_SECONDS = 15 * 60  # §3-5 — 15분 TTL


@dataclass
class AgentResolution:
    domain_code: str
    agent_command: str | None  # 예: "/aegis-security" — None이면 미확정
    source: str  # "search_all" | "fallback_default" | "cache"
    score: float | None
    resolved_at: str


def _is_candidate_command(item: dict) -> bool:
    """§3-2 흐름 3 — 결정적 필터: type=="command" + 경로가 05_commands/slash/aegis-*.md."""
    if item.get("type") != "command":
        return False
    path = item.get("path", "") or item.get("source_ref", "") or item.get("source", "")
    path = path.replace("\\", "/")
    return "05_commands/slash/aegis-" in path and path.endswith(".md")


def _extract_agent_command(item: dict) -> str | None:
    """command 항목에서 슬래시 명령 이름을 뽑아낸다(예: ".../aegis-security.md" → "/aegis-security")."""
    path = item.get("path", "") or item.get("source_ref", "") or item.get("source", "")
    path = path.replace("\\", "/")
    filename = path.rsplit("/", 1)[-1]
    name = filename[: -len(".md")] if filename.endswith(".md") else filename
    return f"/{name}" if name else None


def resolve_agent_for_domain(
    domain_code: str,
    search_fn: Callable[[str], list[dict]],
    cache: dict | None = None,
    now_fn: Callable[[], float] = time.monotonic,
) -> AgentResolution:
    """배차 시점마다 호출 — 정적 테이블 참조 금지(설계서 §3-2).

    1) 캐시 확인(TTL 15분) → 있으면 source="cache"로 즉시 반환
    2) search_fn(DOMAIN_QUERY_HINT[domain_code]) 호출(실제로는 mcp__aegis__search_all)
    3) type=="command" + 경로가 05_commands/slash/aegis-*.md인 항목만 필터
    4) 필터 결과가 1건 이상이면 점수 최상위 채택, source="search_all"
    5) 필터 결과가 0건이면 §3-4 폴백 기본값 사용, source="fallback_default"

    cache는 호출자가 유지하는 dict({domain_code: (AgentResolution, cached_at_monotonic)}) —
    이 함수가 새로 만들지 않고 in-place로 갱신한다(여러 호출 간 캐시를 공유하기 위함).
    """
    now = now_fn()
    if cache is not None and domain_code in cache:
        cached_resolution, cached_at = cache[domain_code]
        if now - cached_at < _TTL_SECONDS:
            return AgentResolution(
                domain_code=domain_code,
                agent_command=cached_resolution.agent_command,
                source="cache",
                score=cached_resolution.score,
                resolved_at=cached_resolution.resolved_at,
            )

    query = DOMAIN_QUERY_HINT.get(domain_code)
    resolved_at = datetime.now(timezone.utc).isoformat()

    results = search_fn(query) if query is not None else []
    candidates = [item for item in results if _is_candidate_command(item)]

    if candidates:
        best = max(candidates, key=lambda item: item.get("score", 0.0))
        resolution = AgentResolution(
            domain_code=domain_code,
            agent_command=_extract_agent_command(best),
            source="search_all",
            score=best.get("score"),
            resolved_at=resolved_at,
        )
    else:
        resolution = AgentResolution(
            domain_code=domain_code,
            agent_command=_FALLBACK_DEFAULT.get(domain_code),
            source="fallback_default",
            score=None,
            resolved_at=resolved_at,
        )

    if cache is not None:
        cache[domain_code] = (resolution, now)

    return resolution
