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

    [2026-07-26 실측 확인] `backend/adapters/llm/ollama_semantic_judge.py`의
    `OllamaSemanticJudge`(청크경계 판정용, `heading_splitter.py`에 실배선됨)와 목적이
    유사(둘 다 LLM 기반 관계판단)하나 별도 용도다 — 저건 "문서 내부" 섹션 간 관계
    (continues/references/... 청킹 경계용), 이건 "문서 간" 관계 추출(Phase 3, 그래프
    엣지 생성용)이며 현재 호출부가 없다(과장 금지, "곧 구현 예정"이 아니라 현재 상태를
    있는 그대로 밝힘 — T98 AIP). 연결하려면 이 함수의 `llm_judge` 콜백 자리에
    `OllamaSemanticJudge`류 어댑터를 감싸는 함수(입력 시그니처를
    `(chunk_a, chunk_b) -> (관계종류, 신뢰도)`로 맞춘 어댑터)를 주입하면 된다.
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
