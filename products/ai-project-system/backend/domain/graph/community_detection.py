"""[Phase 3 후속 — D-0993d22f] Community Detection — god-node 완화·지식 클러스터링.

00_DESIGN_TOC.md Phase 3 리스크 대응 항목("그래프 복잡도 폭증 → 미구현, AEGIS 자체 graphify
스킬의 검증된 개념을 향후 참조 대상으로만 기록")을 실제로 구현한다.

[2026-07-25 실측 대조 보완] AEGIS 자체 graphify 패키지(`graphify/cluster.py`, 로컬 설치본)를
직접 읽어 대조한 결과, "god-node 완화"의 실제 핵심은 커뮤니티 탐지 자체가 아니라 **전체
그래프의 25% 이상을 차지하는 대형 커뮤니티를 재귀적으로 재분할**하는 로직임을 확인했다 —
최초 구현(Louvain 1회 호출만)에는 이 분할 로직이 빠져 있어 "god-node 완화"라는 목적을
실제로 달성하지 못했다(과장 표현이었음, T98 AIP 위반 소지 — 정정). graspologic(Leiden)은
이 환경에 미설치라 AEGIS 원본처럼 Leiden 우선 시도는 하지 않고 Louvain만 사용(범위 밖
의존성 강제 도입 회피, T57 PVS) — 대신 대형 커뮤니티 분할 로직만 그대로 재사용(CRZ).
"""

from __future__ import annotations

import networkx as nx

COMMUNITY_SEED = 42  # Louvain은 휴리스틱(비결정적 초기화 가능) — 재현성을 위해 seed 고정
MAX_COMMUNITY_FRACTION = 0.25  # 이 비율을 넘는 커뮤니티는 재분할 대상(AEGIS graphify와 동일)
MIN_SPLIT_SIZE = 10  # 이보다 작은 커뮤니티는 분할하지 않음(과잉분할 방지, AEGIS graphify와 동일)


def _run_louvain(graph: nx.Graph) -> list[set]:
    if graph.number_of_edges() == 0:
        return [{n} for n in graph.nodes]
    return list(nx.algorithms.community.louvain_communities(graph, weight="weight", seed=COMMUNITY_SEED))


def _split_oversized(graph: nx.Graph, communities: list[set], total_nodes: int) -> list[set]:
    """25% 초과·최소 10노드인 커뮤니티를 서브그래프 위에서 재귀 재분할(god-node 완화 핵심)."""
    result: list[set] = []
    for members in communities:
        if len(members) >= MIN_SPLIT_SIZE and len(members) > total_nodes * MAX_COMMUNITY_FRACTION:
            subgraph = graph.subgraph(members)
            sub_communities = _run_louvain(subgraph)
            if len(sub_communities) > 1:
                # 분할이 실제로 더 잘게 쪼개졌을 때만 재귀 적용(무한루프 방지 — 안 쪼개지면 그대로 채택)
                result.extend(_split_oversized(subgraph, sub_communities, total_nodes))
                continue
        result.append(members)
    return result


def detect_communities(
    node_ids: list[str],
    edges: list[tuple[str, str, float]],
) -> dict[str, int]:
    """node_ids 전체에 대해 community id(0-indexed)를 배정한다.

    edges: (source_id, target_id, weight) 목록 — weight는 보통 Edge.confidence.
    고립 노드(엣지 없음)도 각자 자신만의 community로 배정된다(리스트에서 누락 없음).
    전체 그래프의 25% 이상을 차지하는 대형 커뮤니티는 재귀적으로 재분할한다(god-node 완화).

    community 번호는 크기 내림차순 + 최소 node_id 오름차순으로 정렬해 배정한다 —
    같은 그래프에 대해 매번 같은 번호가 나오도록(엣지 삽입 순서에 의존하지 않는 재현성).
    """
    graph = nx.Graph()
    graph.add_nodes_from(sorted(node_ids))  # AEGIS graphify와 동일 — 입력 순서 무관 안정성
    for source_id, target_id, weight in sorted(edges, key=lambda e: (e[0], e[1])):
        if source_id not in graph or target_id not in graph:
            continue  # 그래프에 없는 노드를 참조하는 엣지는 무시(broken_source_ref 방어, T92 GDI 정신)
        if graph.has_edge(source_id, target_id):
            graph[source_id][target_id]["weight"] += weight
        else:
            graph.add_edge(source_id, target_id, weight=weight)

    communities = _run_louvain(graph)
    communities = _split_oversized(graph, communities, total_nodes=len(node_ids))

    communities.sort(key=lambda c: (-len(c), min(c)))
    assignment: dict[str, int] = {}
    for community_id, members in enumerate(communities):
        for node_id in members:
            assignment[node_id] = community_id
    return assignment
