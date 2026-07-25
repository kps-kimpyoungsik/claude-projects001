import pytest

from backend.domain.requirements.task_state_machine import (
    BLOCKED_CIRCUIT_BREAKER_THRESHOLD,
    HumanReviewRequiredError,
    InvalidTaskStatusError,
    InvalidTaskTransitionError,
    build_status_change_event,
    check_circuit_breaker,
    count_blocked_transitions,
    validate_transition,
)


def test_valid_forward_transition_passes():
    validate_transition("DRAFT", "READY", reason=None)
    validate_transition("READY", "IN_PROGRESS", reason=None)
    validate_transition("IN_PROGRESS", "DONE", reason="테스트 파일 3건 통과 확인")


def test_blocked_transition_requires_reason():
    with pytest.raises(ValueError, match="reason이 필수"):
        validate_transition("READY", "BLOCKED", reason=None)
    validate_transition("READY", "BLOCKED", reason="의존 태스크 미완료")


def test_done_transition_requires_reason():
    """[Phase 5.3 보완] DONE도 근거(reason) 없이는 전이 불가 — 침묵 DONE 오검증 방지."""
    with pytest.raises(ValueError, match="reason이 필수"):
        validate_transition("IN_PROGRESS", "DONE", reason=None)
    validate_transition("IN_PROGRESS", "DONE", reason="완료 근거")


def test_blocked_can_recover_to_ready_or_in_progress():
    validate_transition("BLOCKED", "READY", reason=None)
    validate_transition("BLOCKED", "IN_PROGRESS", reason=None)


def test_invalid_skip_transition_rejected():
    with pytest.raises(InvalidTaskTransitionError):
        validate_transition("DRAFT", "DONE", reason="완료 근거")  # reason 있어도 전이 자체가 금지
    with pytest.raises(InvalidTaskTransitionError):
        validate_transition("DRAFT", "IN_PROGRESS", reason=None)


def test_done_is_terminal():
    with pytest.raises(InvalidTaskTransitionError, match="terminal"):
        validate_transition("DONE", "READY", reason=None)


def test_unknown_status_rejected():
    with pytest.raises(InvalidTaskStatusError):
        validate_transition("DRAFT", "CANCELLED", reason=None)


def test_build_status_change_event_shape():
    event = build_status_change_event("DRAFT", "READY", actor="hong.gildong", reason=None)
    assert event["from_status"] == "DRAFT"
    assert event["to_status"] == "READY"
    assert event["actor"] == "hong.gildong"
    assert event["ts"]


def test_count_blocked_transitions():
    history = [
        {"to_status": "READY"},
        {"to_status": "BLOCKED"},
        {"to_status": "READY"},
        {"to_status": "BLOCKED"},
    ]
    assert count_blocked_transitions(history) == 2
    assert count_blocked_transitions([]) == 0


def test_circuit_breaker_blocks_when_escalated_and_target_not_blocked():
    with pytest.raises(HumanReviewRequiredError):
        check_circuit_breaker(needs_escalation=True, override_escalation=False, to_status="READY")


def test_circuit_breaker_allows_reentering_blocked_without_override():
    """이미 트립된 상태에서 다시 BLOCKED로 가는 것(같은 사고 재확인)은 악화가 아니므로 허용."""
    check_circuit_breaker(needs_escalation=True, override_escalation=False, to_status="BLOCKED")


def test_circuit_breaker_allows_with_override():
    check_circuit_breaker(needs_escalation=True, override_escalation=True, to_status="READY")


def test_circuit_breaker_noop_when_not_escalated():
    check_circuit_breaker(needs_escalation=False, override_escalation=False, to_status="READY")


def test_circuit_breaker_threshold_constant_is_positive():
    assert BLOCKED_CIRCUIT_BREAKER_THRESHOLD > 0
