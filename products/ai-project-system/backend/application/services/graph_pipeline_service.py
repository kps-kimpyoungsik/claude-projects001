"""[Phase 3.3] 지식 신경망 맵핑 파이프라인 — .graphify-out/graph.json 병합.

포맷: 단순 JSON(노드/엣지 배열) — 설계 명세의 "JSON-LD 또는 그래프DB"중 가장 단순하고
의존성 없는 형태를 우선 채택한다(운영 확장 시 그래프DB 마이그레이션은 후속 결정).
AEGIS 자체 graphify 스킬이 이미 검증한 community-detection/god-node 완화 개념을
"재사용 대상"으로만 참조하고, 그 알고리즘 구현 자체는 이 스캐폴딩 범위 밖이다(과장 금지).
"""

import json
from dataclasses import asdict
from pathlib import Path

from backend.domain.graph.entities import Edge, Node

GOD_NODE_EDGE_THRESHOLD = 50  # 이 이상 연결된 노드는 god-node 후보로 플래그만 (자동 분할은 미구현)


def parity_check(edge: Edge, policies: list[str]) -> tuple[bool, str]:
    """지식 병합 전 정책 위배 여부 확인 (governance/constitution/ 정책 기준).

    policies가 비어 있으면(이 프로젝트는 아직 헌법 파일이 없음) "정책 없음 — 통과"로
    정직하게 표기한다. 정책이 있어도 이 스캐폴딩은 텍스트 매칭 수준의 최소 구현이며,
    실제 의미 기반 상충 판정은 LLM 판단이 필요하다(semantic_extractor와 동일 한계).
    """
    if not policies:
        return True, "정책 없음(governance/constitution/ 비어있음) — 통과"
    for p in policies:
        if p and p in (edge.metadata or {}).get("text", ""):
            return False, f"정책 위배 후보: {p}"
    return True, "텍스트 매칭 기준 위배 없음"


def _edge_key(e: dict) -> tuple:
    kind = e["kind"]
    kind = kind.value if hasattr(kind, "value") else kind  # enum -> plain str (깨끗한 로그/JSON 표기)
    return (e["source_id"], e["target_id"], kind)


def merge_into_graph(
    graph_out_path: Path,
    nodes: list[Node],
    edges: list[Edge],
    policies: list[str] | None = None,
) -> dict:
    """새 노드/엣지를 기존 graph.json에 병합 (온톨로지 검증: 중복노드/중복엣지/정책위배 거부).

    - 중복 노드: node_id 동일 → 무시(기존 로직). label+kind 동일 & node_id 다름 →
      "duplicate_node_candidates"에 표시만(자동 병합은 하지 않음 — 오판단 시 데이터 손실 위험).
    - 중복 엣지: (source_id, target_id, kind) 동일 조합이 이미 있으면 거부 + 사유 기록.
    - parity_check 실패 edge도 동일하게 거부 + 사유 기록.
    """
    policies = policies or []
    graph_out_path.parent.mkdir(parents=True, exist_ok=True)

    if graph_out_path.exists():
        graph = json.loads(graph_out_path.read_text(encoding="utf-8"))
    else:
        graph = {"nodes": [], "edges": [], "rejected_edges": [], "duplicate_node_candidates": []}
    graph.setdefault("duplicate_node_candidates", [])

    existing_node_ids = {n["node_id"] for n in graph["nodes"]}
    existing_label_kind = {(n["kind"], n["label"]) for n in graph["nodes"]}
    for n in nodes:
        if n.node_id in existing_node_ids:
            continue
        if (n.kind.value if hasattr(n.kind, "value") else n.kind, n.label) in existing_label_kind:
            graph["duplicate_node_candidates"].append(asdict(n))
        graph["nodes"].append(asdict(n))
        existing_node_ids.add(n.node_id)
        existing_label_kind.add((n.kind.value if hasattr(n.kind, "value") else n.kind, n.label))

    existing_edge_keys = {_edge_key(e) for e in graph["edges"]}
    for e in edges:
        e_dict = asdict(e)
        key = _edge_key(e_dict)
        if key in existing_edge_keys:
            graph["rejected_edges"].append({**e_dict, "reject_reason": f"중복 엣지(온톨로지 규칙 위반): {key}"})
            continue
        ok, reason = parity_check(e, policies)
        if ok:
            graph["edges"].append(e_dict)
            existing_edge_keys.add(key)
        else:
            graph["rejected_edges"].append({**e_dict, "reject_reason": reason})

    # god-node 후보 플래그 (분할은 미구현 — 표시만)
    degree: dict[str, int] = {}
    for e in graph["edges"]:
        degree[e["source_id"]] = degree.get(e["source_id"], 0) + 1
        degree[e["target_id"]] = degree.get(e["target_id"], 0) + 1
    god_node_candidates = [nid for nid, d in degree.items() if d >= GOD_NODE_EDGE_THRESHOLD]
    graph["god_node_candidates"] = god_node_candidates

    graph_out_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    return graph
