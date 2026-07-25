"""[Phase 2 후속] 의미 경계·관계 판단 표준 포트 (2026-07-22).

`heading_splitter.py`의 SemanticBoundarySplitter가 의존하는 인터페이스 — 실제 LLM 호출은
`backend/adapters/llm/ollama_semantic_judge.py`(구현체)가 담당한다(Port/Adapter 원칙,
docx_adapter.py 등 기존 파서 어댑터와 동일 패턴).

사용자 지시(2026-07-22): "LLM 연동해서 청킹 퀄리티를 끌어올려야 한다 / 문서 안에서의 관계
판단도 해야 한다 / 출처가 확실해야 한다" — 이 3원칙을 인터페이스에 그대로 반영한다:
①judge()가 LLM 판단을 호출 ②ChunkRelationship으로 섹션 간 관계 표현
③모든 관계는 evidence(원문 발췌)+정확한 char 위치를 필수로 가진다(구현체가 원문에 실제
존재하지 않는 evidence는 반려해야 함 — 할루시네이션 방지, T98 AIP).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ChunkRelationship:
    from_index: int
    to_index: int
    relation_type: str  # "continues" | "references" | "elaborates" | "contradicts" | "summarizes"
    evidence: str  # 원문에서 그대로 인용한 근거 문구 — 출처 확실성 요구사항의 핵심
    evidence_char_start: int
    evidence_char_end: int
    confidence: float


@dataclass
class SemanticJudgment:
    merged_boundaries: list[int]
    relationships: list[ChunkRelationship] = field(default_factory=list)
    model_name: str = ""
    raw_confidence: float = 0.0


class SemanticJudgePort(ABC):
    @abstractmethod
    def judge(self, sections: list[dict]) -> SemanticJudgment:
        """sections: HeadingBoundarySplitter.split_with_spans() 결과와 동일 스키마
        (content/char_start/char_end/heading_path 키 보유).

        구현체는 각 관계에 evidence(원문 발췌)를 채워야 하며, 그 evidence가 실제로
        해당 from_index 섹션 본문에 존재하지 않으면 그 관계를 반환하지 않아야 한다
        (출처 확실성 — 호출자가 이를 다시 검증하지 않아도 되도록 구현체 책임으로 강제).
        """
        raise NotImplementedError
