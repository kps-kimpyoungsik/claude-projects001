"""[D-0993d22f] merge_into_graph() — community/recency 배선 검증 (신규 테스트, 기존 갭 메움)."""

from datetime import datetime, timedelta, timezone

from backend.application.services.graph_pipeline_service import merge_into_graph
from backend.domain.graph.entities import Edge, EdgeKind, Node, NodeKind


def _node(node_id, label="l"):
    return Node(node_id=node_id, kind=NodeKind.REQUIREMENT, label=label, source_ref="doc.md:1")


def test_merge_stamps_created_at_and_computes_communities_and_recency(tmp_path):
    graph_path = tmp_path / "graph.json"
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    graph = merge_into_graph(
        graph_path,
        nodes=[_node("A"), _node("B")],
        edges=[Edge(edge_id="A->B", kind=EdgeKind.REFINES, source_id="A", target_id="B")],
        now=now,
    )

    assert graph["nodes"][0]["metadata"]["created_at"] == now.isoformat()
    assert set(graph["communities"].keys()) == {"A", "B"}
    assert graph["communities"]["A"] == graph["communities"]["B"]  # 서로 연결된 유일한 두 노드
    assert graph["node_recency_weights"]["A"] == 1.0  # 방금 생성 = 감쇠 없음


def test_re_merge_preserves_original_created_at(tmp_path):
    graph_path = tmp_path / "graph.json"
    first_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    later_time = datetime(2026, 2, 1, tzinfo=timezone.utc)

    merge_into_graph(graph_path, nodes=[_node("A")], edges=[], now=first_time)
    graph = merge_into_graph(graph_path, nodes=[_node("A")], edges=[], now=later_time)
    # A는 이미 존재하므로 nodes 목록엔 추가되지 않음(기존 로직) — created_at 최초값 유지 확인
    stored = next(n for n in graph["nodes"] if n["node_id"] == "A")
    assert stored["metadata"]["created_at"] == first_time.isoformat()
    # 30일 반감기 기준 한 달 뒤 recency는 절반보다 살짝 낮게 감쇠(2026-01-01→02-01=31일)
    assert graph["node_recency_weights"]["A"] < 0.5
