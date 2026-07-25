"""SemanticBoundarySplitter(2026-07-22 실구현) 테스트 — 결정론적 fake judge로 단위테스트,
실제 Ollama 연동은 test_ollama_semantic_judge.py에서 별도 검증(관심사 분리).
"""

from backend.application.ports.semantic_judge_port import (
    ChunkRelationship,
    SemanticJudgePort,
    SemanticJudgment,
)
from backend.domain.chunking.heading_splitter import SemanticBoundarySplitter

DOC = "## A\n첫 섹션 내용입니다.\n\n## B\n둘째 섹션 내용입니다."


class _FakeJudge(SemanticJudgePort):
    """실제 LLM 호출 없이 고정된 관계 1건을 반환하는 테스트 더블."""

    def judge(self, sections):
        evidence = sections[0]["content"].splitlines()[-1]
        return SemanticJudgment(
            merged_boundaries=list(range(len(sections))),
            relationships=[
                ChunkRelationship(
                    from_index=0,
                    to_index=1,
                    relation_type="elaborates",
                    evidence=evidence,
                    evidence_char_start=0,
                    evidence_char_end=len(evidence),
                    confidence=0.9,
                )
            ],
            model_name="fake-test-model",
        )


def test_split_without_judge_behaves_like_heading_splitter():
    splitter = SemanticBoundarySplitter(judge=None)
    sections = splitter.split_with_spans(DOC)
    assert len(sections) == 2
    assert all(s["relationships"] == [] for s in sections)


def test_split_with_judge_attaches_relationships():
    splitter = SemanticBoundarySplitter(judge=_FakeJudge())
    sections = splitter.split_with_spans(DOC)
    assert len(sections) == 2
    assert len(sections[0]["relationships"]) == 1
    rel = sections[0]["relationships"][0]
    assert rel["type"] == "elaborates"
    assert rel["to_index"] == 1
    assert rel["model_name"] == "fake-test-model"
    assert rel["evidence"]  # 출처(evidence) 비어있지 않음


def test_split_plain_returns_content_only():
    splitter = SemanticBoundarySplitter(judge=_FakeJudge())
    result = splitter.split(DOC)
    assert result == ["## A\n첫 섹션 내용입니다.", "## B\n둘째 섹션 내용입니다."]


def test_empty_document_returns_empty_list():
    splitter = SemanticBoundarySplitter(judge=_FakeJudge())
    assert splitter.split_with_spans("") == []
