"""[D-0993d22f] Community Detection — 클러스터 배정 검증."""

import networkx as nx

from backend.domain.graph.community_detection import _split_oversized, detect_communities


def test_isolated_nodes_get_singleton_communities():
    assignment = detect_communities(["A", "B", "C"], edges=[])
    assert len(set(assignment.values())) == 3
    assert set(assignment.keys()) == {"A", "B", "C"}


def test_two_dense_clusters_are_separated():
    node_ids = ["a1", "a2", "a3", "b1", "b2", "b3"]
    edges = [
        ("a1", "a2", 1.0), ("a2", "a3", 1.0), ("a1", "a3", 1.0),
        ("b1", "b2", 1.0), ("b2", "b3", 1.0), ("b1", "b3", 1.0),
    ]
    assignment = detect_communities(node_ids, edges)
    a_communities = {assignment["a1"], assignment["a2"], assignment["a3"]}
    b_communities = {assignment["b1"], assignment["b2"], assignment["b3"]}
    assert len(a_communities) == 1
    assert len(b_communities) == 1
    assert a_communities != b_communities


def test_deterministic_across_repeated_calls():
    node_ids = ["a1", "a2", "a3", "b1", "b2", "b3", "iso"]
    edges = [
        ("a1", "a2", 1.0), ("a2", "a3", 1.0), ("a1", "a3", 1.0),
        ("b1", "b2", 1.0), ("b2", "b3", 1.0), ("b1", "b3", 1.0),
    ]
    first = detect_communities(node_ids, edges)
    second = detect_communities(node_ids, edges)
    assert first == second


def test_edge_referencing_unknown_node_is_ignored():
    assignment = detect_communities(["A", "B"], edges=[("A", "GHOST", 1.0)])
    assert set(assignment.keys()) == {"A", "B"}


def test_oversized_community_is_split_into_substructure():
    """[2026-07-25 실측대조 보완] AEGIS graphify와 동일한 god-node 완화 핵심 —
    25% 초과·최소 10노드인 커뮤니티는 서브그래프 재귀 Louvain으로 재분할되는지 검증."""
    # 두 개의 명확히 분리되는 5-clique를 인위적으로 "하나의 커뮤니티"로 강제 투입해
    # _split_oversized가 그 내부 substructure를 실제로 찾아 쪼개는지 확인한다.
    graph = nx.Graph()
    clique_a = [f"a{i}" for i in range(5)]
    clique_b = [f"b{i}" for i in range(5)]
    for clique in (clique_a, clique_b):
        for i in range(len(clique)):
            for j in range(i + 1, len(clique)):
                graph.add_edge(clique[i], clique[j], weight=1.0)
    graph.add_edge("a0", "b0", weight=0.01)  # 약한 다리 — 두 clique를 하나로 묶는 유일한 연결

    oversized_community = set(clique_a + clique_b)  # 전체 10노드 중 10노드 = 100% > 25%
    split = _split_oversized(graph, [oversized_community], total_nodes=10)

    assert len(split) > 1  # 실제로 쪼개졌는지
    labels = {n: cid for cid, members in enumerate(split) for n in members}
    assert len({labels[n] for n in clique_a}) == 1  # clique_a는 한 커뮤니티로 뭉침
    assert len({labels[n] for n in clique_b}) == 1  # clique_b도 한 커뮤니티로 뭉침
    assert labels[clique_a[0]] != labels[clique_b[0]]  # 서로 다른 커뮤니티로 분리


def test_small_community_below_min_split_size_is_not_split():
    graph = nx.Graph()
    graph.add_edge("x1", "x2", weight=1.0)
    small_community = {"x1", "x2"}
    split = _split_oversized(graph, [small_community], total_nodes=3)
    assert split == [small_community]  # MIN_SPLIT_SIZE(10) 미만 — 분할 대상 아님


def test_duplicate_edge_between_same_pair_accumulates_weight():
    """[커버리지 보완] 같은 (source, target) 쌍이 입력 edges에 두 번 나타나면(예: 여러
    IMPLEMENTS 근거가 같은 노드 쌍을 가리킴) 새 엣지를 추가하는 대신 기존 엣지의
    weight를 누적한다 — 그래프에 중복 엣지가 남지 않아야 한다."""
    assignment = detect_communities(
        ["A", "B"],
        edges=[("A", "B", 0.5), ("A", "B", 0.3)],
    )
    assert set(assignment.keys()) == {"A", "B"}
    assert assignment["A"] == assignment["B"]  # 연결된 두 노드는 같은 커뮤니티
