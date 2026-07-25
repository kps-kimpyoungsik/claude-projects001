"""[Phase 3 후속 — D-0993d22f] Community Detection — god-node 완화·지식 클러스터링.

00_DESIGN_TOC.md Phase 3 리스크 대응 항목("그래프 복잡도 폭증 → 미구현, AEGIS 자체 graphify
스킬의 검증된 개념을 향후 참조 대상으로만 기록")을 실제로 구현한다. AEGIS graphify 스킬이
쓰는 god-node 완화 개념(밀집 클러스터로 그룹핑해 탐색 폭발을 줄임)을 그대로 참조해, 이
프로젝트 그래프(.graphify-out/graph.json)에도 동일 원리를 적용한다 — 신규 알고리즘 발명이
아니라 networkx의 검증된 Louvain 구현(모듈성 최적화)을 재사용한다(CRZ).
"""

from __future__ import annotations

import networkx as nx

COMMUNITY_SEED = 42  # Louvain은 휴리스틱(비결정적 초기화 가능) — 재현성을 위해 seed 고정


def detect_communities(
    node_ids: list[str],
    edges: list[tuple[str, str, float]],
) -> dict[str, int]:
    """node_ids 전체에 대해 community id(0-indexed)를 배정한다.

    edges: (source_id, target_id, weight) 목록 — weight는 보통 Edge.confidence.
    고립 노드(엣지 없음)도 각자 자신만의 community로 배정된다(리스트에서 누락 없음).

    community 번호는 크기 내림차순 + 최소 node_id 오름차순으로 정렬해 배정한다 —
    같은 그래프에 대해 매번 같은 번호가 나오도록(엣지 삽입 순서에 의존하지 않는 재현성).
    """
    graph = nx.Graph()
    graph.add_nodes_from(node_ids)
    for source_id, target_id, weight in edges:
        if source_id not in graph or target_id not in graph:
            continue  # 그래프에 없는 노드를 참조하는 엣지는 무시(broken_source_ref 방어, T92 GDI 정신)
        if graph.has_edge(source_id, target_id):
            graph[source_id][target_id]["weight"] += weight
        else:
            graph.add_edge(source_id, target_id, weight=weight)

    if graph.number_of_edges() == 0:
        # 엣지가 전혀 없으면 모든 노드가 각자 고립 community(Louvain 호출 자체가 무의미)
        communities = [frozenset([n]) for n in node_ids]
    else:
        communities = list(
            nx.algorithms.community.louvain_communities(graph, weight="weight", seed=COMMUNITY_SEED)
        )

    communities.sort(key=lambda c: (-len(c), min(c)))
    assignment: dict[str, int] = {}
    for community_id, members in enumerate(communities):
        for node_id in members:
            assignment[node_id] = community_id
    return assignment
