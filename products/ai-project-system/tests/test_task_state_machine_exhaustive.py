"""[Phase 5.2] 적대적·정적 완전성 검증 — Task 전이 그래프.

개별 케이스 나열이 아니라, TASK_STATUSES x TASK_STATUSES 전 조합(5x5=25건)을 순회하며
ALLOWED_TRANSITIONS과 실제 validate_transition() 판정이 정확히 일치하는지 확인한다.
"정상 케이스 몇 개만 통과하면 끝"이 아니라 "실수로 열어둔 전이·실수로 막은 전이가 하나도
없는가"를 전수 대조하는 것이 이 파일의 목적(T103 AQG §Q-C2 커버리지 누락 방지 정신)."""

import itertools

import pytest

from backend.domain.requirements.task_state_machine import (
    ALLOWED_TRANSITIONS,
    REASON_REQUIRED_STATUSES,
    TASK_STATUSES,
    InvalidTaskTransitionError,
    validate_transition,
)


def _reason_for(to_status: str) -> str | None:
    return "테스트 사유" if to_status in REASON_REQUIRED_STATUSES else None


@pytest.mark.parametrize("from_status,to_status", list(itertools.product(sorted(TASK_STATUSES), repeat=2)))
def test_transition_matrix_matches_allowed_transitions_exactly(from_status, to_status):
    allowed = to_status in ALLOWED_TRANSITIONS.get(from_status, set())
    reason = _reason_for(to_status)

    if allowed:
        validate_transition(from_status, to_status, reason)  # 예외 없이 통과해야 함
    else:
        with pytest.raises(InvalidTaskTransitionError):
            validate_transition(from_status, to_status, reason)


def test_no_status_can_transition_to_itself():
    """자기 자신으로의 '전이'는 어느 상태에서도 허용 전이 그래프에 없어야 한다(의미 없는
    호출을 재확인이 아니라 진짜 전이로 취급하지 않기 위한 설계 불변식 확인)."""
    for status in TASK_STATUSES:
        assert status not in ALLOWED_TRANSITIONS.get(status, set())


def test_done_has_no_outgoing_transitions():
    assert ALLOWED_TRANSITIONS["DONE"] == set()


def test_every_status_covered_in_transition_map():
    """TASK_STATUSES의 모든 값이 ALLOWED_TRANSITIONS의 키로 존재해야 한다(커버리지 누락 방지
    — 신규 상태를 TASK_STATUSES에만 추가하고 전이 그래프에 깜빡 안 넣는 실수를 잡아낸다)."""
    assert set(ALLOWED_TRANSITIONS.keys()) == TASK_STATUSES
