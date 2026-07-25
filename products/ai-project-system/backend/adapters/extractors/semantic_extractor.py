"""[Phase 3.1] Semantic 추출기 — 문서 간 논리적 관계(LLM 추론) 인터페이스.

설계 명세: "문서 간의 논리적 관계는 LLM을 이용해 추론하되, 신뢰도 점수(0.0~1.0)를 함께 기록."
실제 LLM 호출은 이 스캐폴딩 범위 밖이다 — 호출부만 정의하고 NotImplementedError로
명시한다(추정 구현 금지, T98 AIP). 실제 구현 시 `llm_call` 인자로 실제 클라이언트를 주입한다.
"""

from typing import Callable, Protocol

from backend.domain.graph.entities import Edge, EdgeKind


class LLMRelationJudge(Protocol):
    def __call__(self, chunk_a: str, chunk_b: str) -> tuple[str, float]:
        """(관계종류, 신뢰도 0.0~1.0)를 반환하는 콜백 계약."""
        ...


def extract_semantic_relations(
    chunk_pairs: list[tuple[str, str, str, str]],
    llm_judge: Callable[[str, str], tuple[str, float]] | None = None,
) -> list[Edge]:
    """chunk_pairs: (source_id, source_text, target_id, target_text) 목록.

    llm_judge 미주입 시 NotImplementedError — "동작하는 것처럼" 빈 리스트를
    반환하지 않는다(침묵 실패 금지, KH-2026-0755 계열 원칙).
    """
    if llm_judge is None:
        raise NotImplementedError(
            "semantic 추출은 LLM 판단 콜백(llm_judge) 주입이 필요 — 미구현 스텁"
        )

    edges: list[Edge] = []
    for source_id, source_text, target_id, target_text in chunk_pairs:
        kind_raw, confidence = llm_judge(source_text, target_text)
        kind = EdgeKind(kind_raw)  # 미정의 관계종류는 여기서 ValueError로 즉시 실패(침묵 오분류 금지)
        edges.append(
            Edge(
                edge_id=f"{source_id}->{target_id}:{kind.value}",
                kind=kind,
                source_id=source_id,
                target_id=target_id,
                confidence=confidence,
                metadata={"extraction_method": "semantic_llm"},
            )
        )
    return edges
