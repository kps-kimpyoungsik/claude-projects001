"""[Phase 3 x Phase 4 연결] Requirement 노드 + Task-IMPLEMENTS 엣지 팩토리.

00_PROJECT_CONSTITUTION.md §3: "그래프의 핵심 노드는 Requirement(요구사항)와 Policy(제약조건)"
이 모듈은 그 원칙을 실제로 잇는다 — REQ 코드를 그래프의 Requirement 노드로 만들고,
Task가 그 요구사항을 IMPLEMENTS 하는 엣지를 생성해 "요구사항 → 태스크" 추적성을 그래프에 남긴다.

헥사고날 리팩토링(2026-07-19)으로 `backend/domain/graph/entities.py`의 범용 Node/Edge와
별개로 "요구사항"이라는 도메인 개념을 명시적으로 표현하는 얇은 팩토리 계층으로 분리했다 —
Node/Edge 데이터클래스 자체는 재정의하지 않는다(CRZ). REQ ID 문자열 검증은
`backend.domain.requirements.id_format.parse_req_id`를 그대로 재사용한다.
"""

from backend.domain.graph.entities import Edge, EdgeKind, Node, NodeKind
from backend.domain.requirements.id_format import parse_req_id


def make_requirement_node(req_id: str, description: str, source_ref: str) -> Node:
    """REQ 코드(예: REQ-BIZ-SEC-003)를 Requirement 노드로 만든다.

    req_id는 REQ-{문서유형코드}-{영역코드}-{번호} 형식(parse_req_id로 검증)이어야 하고,
    source_ref는 원문 출처(청킹된 문서명·섹션)를 반드시 요구한다 — 근거 없는
    요구사항 노드 생성 금지(00_PROJECT_CONSTITUTION.md §5, "추정 요구사항 생성 금지").
    """
    parse_req_id(req_id)
    if not source_ref:
        raise ValueError(f"{req_id}: source_ref 없는 요구사항 노드 생성 금지(근거 불명)")
    return Node(node_id=req_id, kind=NodeKind.REQUIREMENT, label=description, source_ref=source_ref)


def make_implements_edge(task_id: str, req_id: str) -> Edge:
    """Task가 Requirement를 구현함을 나타내는 IMPLEMENTS 엣지.

    task_id -> req_id 방향(태스크가 요구사항을 구현). 태스크-요구사항 연결은 사람/시스템이
    명시적으로 선언한 사실(task.source_req_ids)이라 confidence=1.0(Deterministic) —
    LLM 추론이 아니므로 semantic_extractor의 신뢰도 개념과 무관하다.
    """
    return Edge(
        edge_id=f"{task_id}::IMPLEMENTS::{req_id}",
        kind=EdgeKind.IMPLEMENTS,
        source_id=task_id,
        target_id=req_id,
        confidence=1.0,
    )
