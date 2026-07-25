"""[D-0993d22f] Community Detection — 클러스터 배정 검증."""

from backend.domain.graph.community_detection import detect_communities


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
