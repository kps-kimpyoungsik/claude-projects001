"""[Phase 4.2] Task 상태 머신 — 순수 로직(I/O 없음).

00_DESIGN_TOC.md Phase 4.2("에이전트 통신 프로토콜(MCP) + 상태 머신")의 실측 갭을 메운다:
`backend/domain/entities/task.py`의 `status` 필드는 지금까지 docstring 주석
("DRAFT -> READY -> IN_PROGRESS -> DONE / BLOCKED")으로만 전이 규칙을 표현했을 뿐,
실제로 그 규칙을 강제하는 코드가 없었다(`TaskStore`에 상태 변경 메서드 자체가 없어
`DRAFT`에서 바로 `DONE`으로 덮어써도 막을 방법이 없었음, 실측: task_store.py 전수 확인).

`backend/adapters/persistence/requirement_store.py`의 `RequirementRecord.set_status()`
+ `status_history` 감사로그 패턴을 그대로 재사용하되(CRZ), Requirement 쪽에는 없던
"어떤 상태에서 어떤 상태로만 갈 수 있는가"(전이 그래프) 검증을 추가한다 — 이것이
Requirement의 평면적 상태값 검증과 Task의 "상태 머신"을 구분짓는 지점이다.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

TASK_STATUSES = {"DRAFT", "READY", "IN_PROGRESS", "DONE", "BLOCKED"}

# 전이 그래프 — Task.status 필드 docstring의 화살표를 그대로 코드화.
# BLOCKED는 READY/IN_PROGRESS 어느 단계에서도 걸릴 수 있고, 해소되면 그 자리로 복귀한다.
# DONE은 종단(terminal) — 재작업이 필요하면 새 Task를 만든다(기존 완료 이력을 덮어쓰지 않음).
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"READY"},
    "READY": {"IN_PROGRESS", "BLOCKED"},
    "IN_PROGRESS": {"DONE", "BLOCKED"},
    "BLOCKED": {"READY", "IN_PROGRESS"},
    "DONE": set(),
}

# BLOCKED 전이는 왜 막혔는지 근거가 없으면 의미가 없다(추정 사유 금지 — RequirementRecord의
# REASON_REQUIRED_STATUSES와 동일 원칙, CRZ).
# [Phase 5.3 보완] DONE도 reason 필수로 추가한다 — "완료됐다"고만 말하고 근거(무엇을 어떻게
# 확인했는지)가 없는 DONE 오검증을 막기 위함(T98 AIP §W-5 물증 원칙과 동일 정신). 이 reason이
# 자동으로 실제 완료 여부를 검증하지는 않는다(정직 표기 — 완전한 검증은 미구현, 최소한 "근거
# 없는 침묵 DONE"만 차단하는 경량 장치).
REASON_REQUIRED_STATUSES = {"BLOCKED", "DONE"}


class InvalidTaskStatusError(ValueError):
    pass


class InvalidTaskTransitionError(ValueError):
    pass


# [Phase 5.3] 서킷 브레이커 — 같은 Task가 BLOCKED에 반복 도달하면(자동 재시도·재배차가
# 매번 같은 이유로 막히는 것으로 해석) 더 이상 자동/자율 진행을 허용하지 않고 사람 검토를
# 강제한다(HITL 승인 게이트). §FRL-1(동일 실패 판정=근본원인 시그니처)과 달리 여기서는
# LLM 판단이 아니라 코드가 기계적으로 횟수만 센다(과도한 자동판정 방지).
BLOCKED_CIRCUIT_BREAKER_THRESHOLD = 3


class HumanReviewRequiredError(ValueError):
    pass


def count_blocked_transitions(status_history: list[dict]) -> int:
    return sum(1 for event in status_history if event.get("to_status") == "BLOCKED")


def check_circuit_breaker(needs_escalation: bool, override_escalation: bool, to_status: str) -> None:
    """[Phase 5.3 HITL 게이트] 이미 서킷 브레이커가 트립된(needs_escalation=True) Task는
    `override_escalation=True`(사람이 검토를 확인)를 명시하지 않는 한 어떤 전이도 거부한다 —
    단, BLOCKED로 재진입(같은 사고 재확인)은 상황 악화가 아니므로 막지 않는다."""
    if needs_escalation and not override_escalation and to_status != "BLOCKED":
        raise HumanReviewRequiredError(
            f"서킷 브레이커 트립 상태(BLOCKED {BLOCKED_CIRCUIT_BREAKER_THRESHOLD}회 이상) — "
            f"사람 검토 없이 전이 불가. override_escalation=True로 검토 완료를 확인해야 함"
        )


@dataclass
class TaskStatusChangeEvent:
    from_status: str
    to_status: str
    actor: str
    reason: str | None = None
    ts: str = ""
    # [2026-07-30 고도화, 02_ENHANCEMENT_REQUIREMENTS.md S3-5] DONE reason은 자유텍스트라
    # "완료됐다"는 자기신고만으로 상태가 바뀔 수 있었다(00_PROJECT_CONSTITUTION §6이 이미
    # 정직하게 자인한 기존 한계). completion_report(호출자가 선택적으로 넘긴 git diff --stat
    # 파싱 결과, `completion_report_service.build_completion_report()` 재사용, CRZ)가 있으면
    # 여기 그대로 첨부하고, evidence_verified는 그 안에 실제 변경 파일이 1건 이상 있을 때만
    # True다 — reason 텍스트를 대체하지 않고 **나란히** 붙는 구조적 근거일 뿐이다(하드 차단
    # 아님, 기존 DONE 전이를 깨지 않는다 — completion_report 미제공 시 이전과 100% 동일 동작).
    completion_report: dict | None = None
    evidence_verified: bool = False


def validate_transition(from_status: str, to_status: str, reason: str | None) -> None:
    """전이 자체가 유효한지만 검증한다(저장은 하지 않음 — 순수 함수, I/O 없음).

    같은 상태로의 "전이"(from == to)는 실수로 인한 무의미한 호출로 보고 막는다 —
    상태 갱신이 아니라 재확인이 목적이라면 호출자가 애초에 set_status를 부르지 않으면 된다.
    """
    if to_status not in TASK_STATUSES:
        raise InvalidTaskStatusError(f"미등록 Task status: {to_status} (허용: {sorted(TASK_STATUSES)})")
    if to_status in REASON_REQUIRED_STATUSES and not reason:
        raise ValueError(f"{to_status} 전이는 reason이 필수다(추정 사유로 채우지 않음)")

    allowed = ALLOWED_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise InvalidTaskTransitionError(
            f"{from_status} -> {to_status} 전이는 허용되지 않음 "
            f"(허용: {sorted(allowed) if allowed else '없음(terminal)'})"
        )


def build_status_change_event(
    from_status: str,
    to_status: str,
    actor: str,
    reason: str | None,
    completion_report: dict | None = None,
) -> dict:
    """검증 통과 후 감사로그 이벤트를 만든다 — 저장(append)은 TaskStore(adapter) 책임.

    `completion_report`(선택)가 있고 `files_changed`가 1건 이상이면 `evidence_verified=True` —
    "reason 텍스트만 있고 실제 diff 근거가 없는 DONE"과 "실제 변경분과 함께 보고된 DONE"을
    감사로그 조회 시점에 구분할 수 있게 한다(추정 검증 아님, 있는 그대로 정직 표기 — T98 AIP).
    """
    evidence_verified = bool(completion_report and completion_report.get("files_changed"))
    event = TaskStatusChangeEvent(
        from_status=from_status,
        to_status=to_status,
        actor=actor,
        reason=reason,
        ts=datetime.now(timezone.utc).isoformat(),
        completion_report=completion_report,
        evidence_verified=evidence_verified,
    )
    return asdict(event)
