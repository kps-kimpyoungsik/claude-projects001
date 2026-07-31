"""[D-0993d22f] merge_into_graph() — community/recency 배선 검증 (신규 테스트, 기존 갭 메움)."""

from datetime import datetime, timedelta, timezone

from backend.application.services.graph_pipeline_service import merge_into_graph, parity_check
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


def test_parity_check_flags_edge_matching_policy_text():
    """[커버리지 보완] policies에 있는 문구가 edge.metadata['text']에 포함되면 위배 후보로
    거부된다."""
    edge = Edge(edge_id="A->B", kind=EdgeKind.REFINES, source_id="A", target_id="B", metadata={"text": "금지된 표현 포함"})
    ok, reason = parity_check(edge, ["금지된 표현"])
    assert ok is False
    assert "정책 위배 후보" in reason


def test_parity_check_passes_when_policies_present_but_no_match():
    """[커버리지 보완] policies가 있어도 edge 텍스트에 매칭되는 문구가 없으면 통과한다."""
    edge = Edge(edge_id="A->B", kind=EdgeKind.REFINES, source_id="A", target_id="B", metadata={"text": "평범한 내용"})
    ok, reason = parity_check(edge, ["금지된 표현"])
    assert ok is True
    assert "위배 없음" in reason


def test_merge_rejects_edge_violating_policy(tmp_path):
    """[커버리지 보완] merge_into_graph()에 policies를 넘기면 위배 edge는 edges가 아니라
    rejected_edges에 사유와 함께 들어간다."""
    graph_path = tmp_path / "graph.json"
    edge = Edge(edge_id="A->B", kind=EdgeKind.REFINES, source_id="A", target_id="B", metadata={"text": "금지된 표현"})

    graph = merge_into_graph(
        graph_path,
        nodes=[_node("A"), _node("B")],
        edges=[edge],
        policies=["금지된 표현"],
    )
    assert graph["edges"] == []
    assert len(graph["rejected_edges"]) == 1
    assert "정책 위배 후보" in graph["rejected_edges"][0]["reject_reason"]


def test_merge_rejects_duplicate_edge_on_second_merge(tmp_path):
    """[커버리지 보완] 같은 (source_id, target_id, kind) 조합의 엣지를 두 번 병합하면
    두 번째는 rejected_edges에 '중복 엣지' 사유로 들어가고 edges에는 1건만 남는다."""
    graph_path = tmp_path / "graph.json"
    edge = Edge(edge_id="A->B", kind=EdgeKind.REFINES, source_id="A", target_id="B")

    merge_into_graph(graph_path, nodes=[_node("A"), _node("B")], edges=[edge])
    graph = merge_into_graph(graph_path, nodes=[_node("A"), _node("B")], edges=[edge])

    assert len(graph["edges"]) == 1
    assert len(graph["rejected_edges"]) == 1
    assert "중복 엣지" in graph["rejected_edges"][0]["reject_reason"]
