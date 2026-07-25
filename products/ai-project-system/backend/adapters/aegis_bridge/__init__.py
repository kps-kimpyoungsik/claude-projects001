"""aegis_bridge — 이 프로젝트가 AEGIS(MCP·HTTP 인터페이스)와 맞닿는 경계 어댑터 계층.

이 패키지의 어댑터는 항상 `agent_dispatch_resolver.resolve_agent_for_domain()`이 요구하는
`search_fn: Callable[[str], list[dict]]` 포트 시그니처를 구현한다 — 도메인/애플리케이션
계층은 이 패키지의 구체 구현을 모른 채 포트 인터페이스로만 의존한다(헥사고날 adapters→domain
단방향 원칙).
"""
