"""디자인 시안 선행 게이트 판정 함수 회귀 테스트 —
plans/_plan/01_PHASE1_DATA_MODEL.md §5-2 pseudocode 그대로 구현했는지 확인한다.
"""

from backend.domain.requirements.design_gate import (
    BLOCK_MANDATORY,
    PASS,
    WARN_STRATEGIC,
    evaluate_design_draft_gate,
)


def test_override_wins_even_when_project_confirmed():
    """§5-2 규칙 2) — override=True면 project 확정 여부와 무관하게 원래 규칙이 작동한다."""
    result = evaluate_design_draft_gate(
        design_draft_gate="MANDATORY",
        design_draft_gate_override=True,
        project_design_draft_confirmed=True,
    )
    assert result == BLOCK_MANDATORY


def test_project_confirmed_auto_passes_when_no_override():
    """§5-2 규칙 3) — override가 없고 project_design_draft_confirmed=True면 자동 통과."""
    result = evaluate_design_draft_gate(
        design_draft_gate="MANDATORY",
        design_draft_gate_override=False,
        project_design_draft_confirmed=True,
    )
    assert result == PASS


def test_normal_rule_fallback_mandatory_blocks():
    """§5-2 규칙 4) — override 없음 + project 미확정 → 원래 규칙(§5-2-A) 그대로."""
    result = evaluate_design_draft_gate(
        design_draft_gate="MANDATORY",
        design_draft_gate_override=False,
        project_design_draft_confirmed=False,
    )
    assert result == BLOCK_MANDATORY


def test_normal_rule_fallback_strategic_mandatory_warns_not_blocks():
    """§5-2-A — STRATEGIC_MANDATORY는 경고 배너일 뿐 강제가 아니다(MANDATORY와 차등)."""
    result = evaluate_design_draft_gate(
        design_draft_gate="STRATEGIC_MANDATORY",
        design_draft_gate_override=False,
        project_design_draft_confirmed=False,
    )
    assert result == WARN_STRATEGIC


def test_not_mandatory_never_gates_regardless_of_flags():
    """§5-2 규칙 1) — NOT_MANDATORY는 애초에 게이트 대상이 아니다."""
    result = evaluate_design_draft_gate(
        design_draft_gate="NOT_MANDATORY",
        design_draft_gate_override=True,
        project_design_draft_confirmed=False,
    )
    assert result == PASS


def test_none_gate_value_passes():
    result = evaluate_design_draft_gate(
        design_draft_gate=None,
        design_draft_gate_override=False,
        project_design_draft_confirmed=False,
    )
    assert result == PASS
