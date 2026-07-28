"""`backend/adapters/extractors/semantic_extractor.py` 단위 테스트.

이 모듈은 (a) 카테고리 — 완결된 실 구현체다(외부 LLM 서버 의존 없이 콜백 계약으로
동작). `llm_judge` 미주입 시 명시적 `NotImplementedError`(침묵 실패 금지)와, 주입 시
`Edge` 리스트 생성 로직을 검증한다.
"""

import pytest

from backend.adapters.extractors.semantic_extractor import extract_semantic_relations
from backend.domain.graph.entities import EdgeKind


def test_raises_without_llm_judge():
    with pytest.raises(NotImplementedError):
        extract_semantic_relations([("a", "텍스트a", "b", "텍스트b")])


def test_builds_edges_from_llm_judge_callback():
    def fake_judge(chunk_a: str, chunk_b: str):
        return ("IMPLEMENTS", 0.8)

    edges = extract_semantic_relations(
        [("req-1", "요구사항 텍스트", "code-1", "코드 텍스트")],
        llm_judge=fake_judge,
    )
    assert len(edges) == 1
    edge = edges[0]
    assert edge.kind == EdgeKind.IMPLEMENTS
    assert edge.source_id == "req-1"
    assert edge.target_id == "code-1"
    assert edge.confidence == 0.8
    assert edge.edge_id == "req-1->code-1:IMPLEMENTS"
    assert edge.metadata == {"extraction_method": "semantic_llm"}


def test_multiple_chunk_pairs_produce_multiple_edges():
    calls = []

    def fake_judge(chunk_a: str, chunk_b: str):
        calls.append((chunk_a, chunk_b))
        return ("CALLS", 1.0)

    pairs = [
        ("a", "텍스트a", "b", "텍스트b"),
        ("c", "텍스트c", "d", "텍스트d"),
    ]
    edges = extract_semantic_relations(pairs, llm_judge=fake_judge)
    assert len(edges) == 2
    assert len(calls) == 2


def test_unknown_relation_kind_raises_value_error():
    def fake_judge(chunk_a: str, chunk_b: str):
        return ("NOT_A_REAL_KIND", 0.5)

    with pytest.raises(ValueError):
        extract_semantic_relations([("a", "x", "b", "y")], llm_judge=fake_judge)


def test_confidence_out_of_range_raises_value_error():
    def fake_judge(chunk_a: str, chunk_b: str):
        return ("REFINES", 1.5)

    with pytest.raises(ValueError):
        extract_semantic_relations([("a", "x", "b", "y")], llm_judge=fake_judge)
