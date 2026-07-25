"""[Phase 3.1] Graphify 도메인 모델 — Node/Edge 구조체 정의.

설계 명세 그대로: Node 종류 4개(DocumentChunk/Function/Variable/Requirement/Policy),
Edge 종류 4개(IMPLEMENTS/CONTRADICTS/CALLS/REFINES).
"""

from dataclasses import dataclass, field
from enum import Enum


class NodeKind(str, Enum):
    DOCUMENT_CHUNK = "DocumentChunk"
    FUNCTION = "Function"
    VARIABLE = "Variable"
    REQUIREMENT = "Requirement"
    POLICY = "Policy"


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
