"""[Phase 3 Ext] 우선순위 오케스트레이션 (설계: plans/_plan/06_AGENT_DISPATCH_REPORTING.md §4).

신규 알고리즘 발명 없이 이미 있는 신호(lifecycle_status·needs_escalation·
detect_area_conflicts)만 조합한다. 이 서비스는 "누구에게 배차할지 계획을 세우는" 순수
로직까지만 책임진다 — 실제 `Agent(subagent_type=..., prompt=...)` 호출은 하지 않는다.

판단(설계서에 남기라고 지시된 부분): 설계서 §4 "각 배차는 Agent(...)" 문장은 실행 계층의
일이라고 판단했다 — 이 모듈이 Claude Code의 Agent 툴을 직접 호출하면 순수 도메인/애플리케이션
서비스가 세션 툴(Agent 호출)에 의존하게 되어 테스트 불가능해지고, 헥사고날 아키텍처의
adapters→domain 단방향 의존 원칙과도 어긋난다. 그래서 `dispatch_tasks()`는 "무엇을 누구에게
배차할지"의 계획(dict 리스트)만 반환하고, 그 계획을 소비해 실제 Agent()를 호출하는 것은
상위 오케스트레이터(세션/커맨드 레벨)의 몫으로 분리했다.
"""

from backend.adapters.persistence.requirement_store import RequirementRecord
from backend.application.ports.task_store_port import TaskStorePort
from backend.domain.entities.task import Task
from backend.domain.requirements.conflict_detection import detect_area_conflicts

_ACCEPTED_LIKE_STATUSES = {"ACCEPTED", "IN_PROGRESS", "IMPLEMENTED", "VERIFIED"}


def compute_priority(task: Task, all_requirements: list[RequirementRecord]) -> int:
    """우선순위 점수 — 낮을수록 먼저 처리 (설계서 §4 의사코드 그대로).

    1) task.source_req_ids가 참조하는 REQ 중 하나라도 lifecycle_status가
       ACCEPTED류(ACCEPTED/IN_PROGRESS/IMPLEMENTED/VERIFIED)면 우선(사람이 확정한
       요구사항이 우선) — 그렇지 않으면(예: UNDER_REVIEW만 참조) 후순위.
    2) needs_escalation=True(불충분)면 후순위(설계 구체화 먼저 필요).
    """
    req_by_id = {r.req_id: r for r in all_requirements}
    referenced = [req_by_id[rid] for rid in task.source_req_ids if rid in req_by_id]
    has_accepted_ref = any(r.lifecycle_status in _ACCEPTED_LIKE_STATUSES for r in referenced)

    score = 0
    if not has_accepted_ref:
        score += 100
    if task.needs_escalation:
        score += 1000
    return score


def dispatch_tasks(
    task_store: TaskStorePort,
    all_requirements: list[RequirementRecord],
    resolve_fn,
    usage_log=None,
) -> list[dict]:
    """배차 계획을 세운다 (설계서 §4 배차 흐름 그대로).

    [2026-07-24 고도화] 시그니처를 concrete `TaskStore` 대신 `TaskStorePort`로 교체 —
    이 함수는 `list_all()`만 쓰므로(Port에 이미 정의됨) 실제 구현체가 JSON이든
    PostgreSQL이든 이 서비스 코드는 그대로다(헥사고날 "Port만 보면 교체 가능" 원칙 회복,
    5-agent 진단 architect000 실측 확인 항목).

    TaskStore.list_all() → compute_priority()로 정렬 → detect_area_conflicts()로 그룹핑
      → CLEAR 그룹은 resolve_fn(domain_code)로 조회한 agent로 병렬 배차 표시
      → OVERLAP 그룹(파일 경로가 겹치는 태스크들)은 순차 배차 표시(§PAW-3)

    resolve_fn: (domain_code: str) -> AgentResolution — 실제로는
    agent_dispatch_resolver.resolve_agent_for_domain을 부분 적용해서 넘긴다(포트 주입).

    usage_log: [2026-07-26 배선] `AgentRoleUsageLog` 인스턴스(선택) — 주입되면 이 함수가
    실제로 배차를 확정하는 지점(각 task별 resolve_fn 호출 직후)마다
    `record(domain_code, agent_command, resolution_source, resolved_at)`를 호출해
    "실제로 어떤 agent가 어떤 영역에 쓰였는지"의 ground-truth 이력을 남긴다. 미주입
    시(기존 호출부·테스트) 로깅을 생략한다 — 순수 계획 함수라는 기존 계약을 깨지 않는다
    (하위호환, CRZ — 새 저장 포맷 발명 없이 기존 `AgentRoleUsageLog` 인터페이스 재사용).

    반환값은 실행 계획(dict 리스트)이지 실행 결과가 아니다 — Agent() 호출은 하지 않는다.
    """
    tasks = task_store.list_all()
    tasks.sort(key=lambda t: compute_priority(t, all_requirements))

    conflicts = detect_area_conflicts(tasks)
    overlapping_ids: set[str] = set()
    for pair in conflicts["pairs"]:
        overlapping_ids.add(pair["a"])
        overlapping_ids.add(pair["b"])

    plan = []
    for task in tasks:
        resolution = resolve_fn(task.domain_code)
        if usage_log is not None:
            usage_log.record(
                domain_code=resolution.domain_code,
                agent_command=resolution.agent_command,
                resolution_source=resolution.source,
                resolved_at=resolution.resolved_at,
            )
        is_overlap = task.task_id in overlapping_ids
        plan.append(
            {
                "task_id": task.task_id,
                "domain_code": task.domain_code,
                "priority_score": compute_priority(task, all_requirements),
                "dispatch_mode": "sequential" if is_overlap else "parallel",
                "agent_resolution": resolution,
                # plans/_plan/03_PHASE3_AGENT_GRAPHIFY.md §3-1 프롬프트 조립 공식이
                # 요구하는 두 필드 — dispatch_execution_planner.build_execution_prompts()가
                # Requirement 원문·solution_stack을 조립하려면 이 계획 단계에서부터
                # Task 엔티티가 이미 갖고 있는 값을 실어 날라야 한다(신규 조회 없음, CRZ).
                "source_req_ids": list(task.source_req_ids),
                "solution_stack": list(task.solution_stack),
            }
        )
    return plan


# §10-2 — Task.status(DRAFT→READY→IN_PROGRESS→DONE/BLOCKED)를 요구사항 관점 work_status로
# 집계할 때의 정직성 우선순위(설계서 §10-2 표 그대로): 문제 은폐 방지를 위해 BLOCKED를
# 최우선, 전부 완료된 경우에만 DONE을 매긴다(부분 완료는 낙관적으로 앞당기지 않음, T98 AIP).
_WORK_STATUS_PRIORITY = ["BLOCKED", "IN_PROGRESS", "DISPATCHED", "DONE", "NOT_DISPATCHED"]


def _aggregate_work_status(task_statuses: list[str]) -> str:
    """참조 Task들의 `Task.status` 집합 → REQ 관점 `work_status` 하나로 집계 (§10-2 표)."""
    if not task_statuses:
        return "NOT_DISPATCHED"

    mapped: set[str] = set()
    for status in task_statuses:
        if status == "BLOCKED":
            mapped.add("BLOCKED")
        elif status == "IN_PROGRESS":
            mapped.add("IN_PROGRESS")
        elif status in ("DRAFT", "READY"):
            mapped.add("DISPATCHED")
        elif status == "DONE":
            mapped.add("DONE")

    if "DONE" in mapped and len(mapped) == 1:
        return "DONE"
    for candidate in _WORK_STATUS_PRIORITY:
        if candidate in mapped and candidate != "DONE":
            return candidate
    return "NOT_DISPATCHED"


def sync_requirement_work_status(
    requirement_store, task_store, dispatch_plan: list[dict],
) -> None:
    """§10-3 — 배차 "계획"(dispatch_tasks()의 반환값)을 `RequirementRecord`에 되먹임한다.

    신규 폴링 루프를 만들지 않는다 — §5(작업상태 확인)의 기존 폴링 지점에서 함께 호출되는
    것을 전제로 한 얇은 동기화 함수다(CRZ). dispatch_plan의 각 항목(task_id·agent_resolution·
    source_req_ids)과 TaskStore.list_all()의 최신 Task.status를 조합해, 각 REQ가 참조되는
    모든 Task의 status를 모아 §10-2 집계 규칙으로 work_status·assigned_agent_command를
    계산하고 RequirementStore.set_work_status()로 반영한다.
    """
    tasks_by_id = {t.task_id: t for t in task_store.list_all()}

    # REQ별로 (참조 Task.status 목록, 그 Task들에 배차된 agent_command 목록)을 모은다.
    req_task_statuses: dict[str, list[str]] = {}
    req_agent_commands: dict[str, list[str]] = {}
    for plan_item in dispatch_plan:
        task = tasks_by_id.get(plan_item["task_id"])
        task_status = task.status if task is not None else "DRAFT"
        resolution = plan_item.get("agent_resolution")
        agent_command = getattr(resolution, "agent_command", None) if resolution is not None else None
        for req_id in plan_item.get("source_req_ids", []):
            req_task_statuses.setdefault(req_id, []).append(task_status)
            if agent_command:
                req_agent_commands.setdefault(req_id, []).append(agent_command)

    for req in requirement_store.list_all():
        statuses = req_task_statuses.get(req.req_id, [])
        work_status = _aggregate_work_status(statuses)
        commands = req_agent_commands.get(req.req_id, [])
        # 여러 Task가 같은 REQ를 참조해 서로 다른 agent에 배차됐을 수 있으므로, 표시는
        # 가장 최근(마지막) 배차 결과 하나만 남긴다(§10-2는 REQ당 단일 배지를 전제).
        assigned_agent_command = commands[-1] if commands else None
        requirement_store.set_work_status(req.req_id, work_status, assigned_agent_command)
