"""[Phase 3.1] Graphify 도메인 모델 — Node/Edge 구조체 정의.

설계 명세 원안: Node 종류 4개(DocumentChunk/Function/Variable/Requirement/Policy),
Edge 종류 4개(IMPLEMENTS/CONTRADICTS/CALLS/REFINES).

[2026-07-29 배선, directive D-eebcef47] `NodeKind.TASK` 추가 — `requirement.py.
make_implements_edge(task_id, req_id)`가 이미 존재했으나 그래프에 TASK 종류 노드가
없어 엣지의 source_id(task_id)가 가리키는 노드가 그래프에 없는 고아 엣지(T92 GDI
위반)를 만들 수 있었다. 사용자 결정(방향 ①): Task 생성 시점에 Task 노드도 함께
merge해 완전한 그래프 표현을 만든다 — `backend.domain.entities.task.make_task_node()`
참조.
"""

from dataclasses import dataclass, field
from enum import Enum


class NodeKind(str, Enum):
    DOCUMENT_CHUNK = "DocumentChunk"
    FUNCTION = "Function"
    VARIABLE = "Variable"
    REQUIREMENT = "Requirement"
    POLICY = "Policy"
    TASK = "Task"  # [directive D-eebcef47] make_implements_edge(task_id, req_id)의 task_id
    # 쪽이 그래프에 실재해야 고아 엣지(T92 GDI)가 생기지 않는다.


class EdgeKind(str, Enum):
    IMPLEMENTS = "IMPLEMENTS"      # 코드 - 요구사항
    CONTRADICTS = "CONTRADICTS"    # 정책 상충
    CALLS = "CALLS"                # 함수 호출
    REFINES = "REFINES"            # 설계 개선


@dataclass
class Node:
    node_id: str
    kind: NodeKind
    label: str
    source_ref: str  # 파일 경로:라인 등 — 실측 없는 노드 생성 금지(T59 CFD)
    metadata: dict = field(default_factory=dict)


@dataclass
class Edge:
    edge_id: str
    kind: EdgeKind
    source_id: str
    target_id: str
    confidence: float = 1.0  # Deterministic 추출=1.0, Semantic 추출=0.0~1.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence는 0.0~1.0이어야 함: {self.confidence}")
