"""[Phase 3 Ext] 배차 계획 → 실행 프롬프트 조립 (설계: plans/_plan/06_AGENT_DISPATCH_REPORTING.md §4 후속).

`task_dispatch_service.dispatch_tasks()`가 반환하는 배차 **계획**(dict 리스트, 실행 아님)을
입력받아, 각 배차 항목을 LLM 세션이 실제로 `Agent(subagent_type=..., prompt=...)` 호출 또는
슬래시 커맨드(`/aegis-security` 등)로 실행하기 위해 필요한 **완전한 프롬프트 텍스트**를
문자열로 조립해 반환한다.

이 모듈이 하지 않는 것(할 수 없는 것): 실제 `Agent()` 호출. Claude Code의 Agent 툴은
LLM 세션 툴 콜이지 이 프로세스가 임포트해서 부를 수 있는 Python API가 아니다(설계서
§4 지시 그대로 — `task_dispatch_service.py` 상단 docstring과 동일한 판단). 그래서 이 함수의
출력은 "다음에 무엇을 어떻게 호출해야 하는지 적힌 문자열"이 이 코드가 낼 수 있는 최대치이고,
실제 실행(Agent 호출 또는 슬래시 커맨드 실행)은 이 함수의 출력을 받은 사람 또는 LLM 세션이
수행해야 한다.
"""

from __future__ import annotations

from typing import Any, Callable

from backend.adapters.persistence.requirement_store import RequirementRecord

# plans/_plan/03_PHASE3_AGENT_GRAPHIFY.md §3-1 프롬프트 조립 공식의 두 번째·세 번째 항
# ("source_req_ids로 연결된 Requirement 전문" + "solution_stack")을 채우기 위한 조회 함수
# 타입. 이 모듈(application 계층)이 RequirementRecord(adapters 계층) 타입을 참조하는 것은
# 헥사고날 방향상 정상이다 — 금지되는 것은 domain→adapters 역방향 의존이지 application→
# adapters 순방향 의존이 아니다(00_PROJECT_CONSTITUTION.md 경계 규칙, 직전 사이클에서
# agent_dispatch_resolver.py가 확인한 것과 동일 판단). 실제 값 주입은 이 함수를 소비하는
# 쪽(오케스트레이터/커맨드 레벨)이 RequirementStore.list_all()을 미리 dict로 인덱싱해
# 부분 적용한 조회 함수를 넘기는 방식을 기대한다 — 이 모듈 자체는 여전히 DB/파일 접근을
# 하지 않는 순수 함수로 남는다(설계서 §3-2 "새 데이터 모델 발명 없음" 원칙 유지).
RequirementLookup = Callable[[str], "RequirementRecord | None"]


def _resolution_field(resolution: Any, field: str, default: Any = None) -> Any:
    """agent_resolution이 `AgentResolution` 데이터클래스든(정상 경로) dict든
    (예: JSON 왕복을 거친 배차 계획) 동일하게 필드를 꺼낸다."""
    if isinstance(resolution, dict):
        return resolution.get(field, default)
    return getattr(resolution, field, default)


def _derive_subagent_type_hint(agent_command: str | None) -> str:
    """agent_command(예: "/aegis-security")에서 Agent(subagent_type=...) 힌트를 뽑는다.

    이 프로젝트의 배차는 원래 AEGIS 슬래시 커맨드(`/aegis-*`)를 가리키므로, 실제
    실행 경로는 그 슬래시 커맨드를 그대로 호출하는 쪽이 우선이다. subagent_type
    폼으로 실행해야 하는 상위 세션을 위해 커맨드 이름에서 접두 `/`만 제거한 문자열을
    힌트로 제공한다 — 미확정(None)이면 범용 에이전트로 폴백한다.
    """
    if not agent_command:
        return "general-purpose"
    return agent_command.lstrip("/")


def _mode_note(dispatch_mode: str) -> str:
    if dispatch_mode == "sequential":
        return (
            "이 태스크는 다른 태스크와 impact_scope(파일 경로)가 겹쳐(§PAW-3 충돌 표면) "
            "순차 배차 대상이다 — 겹치는 다른 태스크가 완료된 뒤에 착수해야 한다."
        )
    return "이 태스크는 겹치는 태스크가 없어(CLEAR) 병렬 배차 가능하다."


def _format_source_location(record: RequirementRecord) -> str:
    """설계서 §3-1 "source_location 포함" — 미리보기 화면(2차 설계)이 원문을 하이라이트할
    때 쓰는 것과 동일한 좌표(source_ref/heading_path/char_start·end)를 사람이 읽을 문자열로."""
    parts = [record.source_ref]
    if record.heading_path:
        parts.append(" > ".join(record.heading_path))
    if record.char_start is not None and record.char_end is not None:
        parts.append(f"chars {record.char_start}-{record.char_end}")
    return ", ".join(p for p in parts if p)


def _requirement_block(
    source_req_ids: list[str], requirement_lookup: RequirementLookup | None
) -> str:
    """설계서 §3-1 프롬프트 공식 2번째 항 — Requirement 원문 발췌 + source_location.

    조회 함수가 아예 주입되지 않았거나(하위호환), 특정 req_id가 스토어에 없는 경우
    모두 크래시하지 않고 "원문 조회 불가"로 정직하게 표시한다(T98 AIP — 없는 데이터를
    있는 것처럼 꾸미지 않는다).
    """
    if not source_req_ids:
        return "■ 근거 요구사항: 없음 (source_req_ids 미지정)"
    if requirement_lookup is None:
        return (
            "■ 근거 요구사항: 조회 함수 미제공 — 원문 발췌 불가 "
            f"(source_req_ids={source_req_ids})"
        )

    lines = ["■ 근거 요구사항 원문 발췌:"]
    for req_id in source_req_ids:
        record = requirement_lookup(req_id)
        if record is None:
            lines.append(f"  - {req_id}: 원문 조회 불가 (스토어에 없음)")
            continue
        location = _format_source_location(record)
        lines.append(f"  - {req_id} [{location}]: {record.description}")
    return "\n".join(lines)


def _solution_stack_block(
    task_solution_stack: list[str],
    source_req_ids: list[str],
    requirement_lookup: RequirementLookup | None,
) -> str:
    """설계서 §3-1 프롬프트 공식 3번째 항 — "이 태스크가 어떤 프레임워크 기반이어야
    하는지". Task.solution_stack(1차 설계 §2-4, 이 태스크가 배차 계획 시점에 이미
    갖고 있음)을 우선으로 하되, 근거 Requirement 각각도 자기 solution_stack 필드를
    가지므로(RequirementRecord — 청킹 시점에 이미 태깅됨) 중복 없이 병합해 태스크
    수행자가 "이 요구사항이 지정한 스택"까지 함께 보도록 한다."""
    stacks = list(task_solution_stack or [])
    if requirement_lookup is not None:
        for req_id in source_req_ids or []:
            record = requirement_lookup(req_id)
            if record and record.solution_stack:
                for stack in record.solution_stack:
                    if stack not in stacks:
                        stacks.append(stack)
    if not stacks:
        return "■ solution_stack: 미지정"
    return "■ solution_stack(기반 프레임워크): " + ", ".join(stacks)


def _build_prompt_text(
    task_id: str,
    domain_code: str,
    dispatch_mode: str,
    agent_command: str | None,
    source: str | None,
    score: float | None,
    subagent_type_hint: str,
    requirement_block: str,
    solution_stack_block: str,
) -> str:
    score_note = f", score={score:.2f}" if isinstance(score, (int, float)) else ""
    resolution_note = (
        f"agent_command={agent_command or '미확정'} "
        f"(source={source or 'unknown'}{score_note})"
    )

    return (
        f"[배차 항목] task_id={task_id} domain={domain_code} mode={dispatch_mode}\n"
        f"{resolution_note}\n"
        f"{_mode_note(dispatch_mode)}\n\n"
        f"{requirement_block}\n\n"
        f"{solution_stack_block}\n\n"
        "이 배차 항목을 실행하려면 아래 중 하나로 호출한다:\n"
        f"  1) agent_command가 확정된 경우: 슬래시 커맨드 `{agent_command}` 그대로 실행\n"
        f"  2) subagent_type 폼이 필요한 경우: "
        f'Agent(subagent_type="{subagent_type_hint}", '
        f'prompt="task_id={task_id} (domain={domain_code}) 관련 작업을 수행하라. '
        f'상세는 TaskStore의 해당 태스크 레코드를 조회해 반영하라.")\n\n'
        "주의: 위 텍스트는 조립된 프롬프트 문자열일 뿐이며, 실제 Agent() 호출/슬래시 커맨드 "
        "실행은 이 함수를 소비하는 LLM 세션(또는 사람)이 수행해야 한다 — 이 Python 코드는 "
        "Agent 툴을 직접 호출할 수 없다(설계서 §4 그대로)."
    )


def build_execution_prompts(
    dispatch_plan: list[dict],
    requirement_lookup: RequirementLookup | None = None,
) -> list[dict]:
    """`dispatch_tasks()`의 배차 계획을 받아 실행용 프롬프트 텍스트 리스트로 변환한다.

    plans/_plan/03_PHASE3_AGENT_GRAPHIFY.md §3-1 프롬프트 조립 공식 전체를 채운다:
    Task(title/description/acceptance_criteria는 이 함수 밖 TaskStore 조회 몫으로 남고,
    여기서는) + source_req_ids로 연결된 Requirement 원문(원문 발췌, source_location 포함)
    + solution_stack + (배차 힌트로서) domain_code/dispatch_mode. §2 ProjectDomainSnapshot
    발췌는 그 하위시스템 자체가 미구현이라 이번 사이클 범위 밖이다(설계서 §5 #참조).

    requirement_lookup: (req_id: str) -> RequirementRecord | None. 이 함수는 여전히
    DB/파일 접근을 하지 않는 순수 함수다 — 조회는 호출자가 주입한 함수에 위임한다
    (직전 사이클의 agent_dispatch_resolver 패턴과 동일한 포트 주입 방식, CRZ). 생략하면
    (기본값 None) 요구사항 원문·solution_stack 병합 없이 이전과 동일하게 동작한다
    (하위호환 — 기존 호출부·테스트 무손상).

    반환 각 항목:
      - task_id, domain_code, dispatch_mode: 배차 계획 원본 그대로
      - agent_command: 확정된 슬래시 커맨드(없으면 None)
      - subagent_type_hint: Agent(subagent_type=...) 호출용 힌트 문자열
      - resolution_source: "search_all" | "fallback_default" | "cache"
      - source_req_ids, solution_stack: 배차 계획 원본 그대로(추적용)
      - prompt_text: 사람/LLM 세션이 그대로 읽고 호출을 수행할 수 있는 완전한 텍스트
        (요구사항 원문 발췌 + solution_stack 블록 포함)

    이 함수는 순수 문자열 조립 로직만 수행한다 — Agent() 호출·슬래시 커맨드 실행 둘 다
    하지 않는다.
    """
    prompts: list[dict] = []
    for item in dispatch_plan:
        resolution = item.get("agent_resolution")
        agent_command = _resolution_field(resolution, "agent_command")
        source = _resolution_field(resolution, "source")
        score = _resolution_field(resolution, "score")
        subagent_type_hint = _derive_subagent_type_hint(agent_command)

        source_req_ids = list(item.get("source_req_ids") or [])
        task_solution_stack = list(item.get("solution_stack") or [])

        requirement_block = _requirement_block(source_req_ids, requirement_lookup)
        solution_stack_block = _solution_stack_block(
            task_solution_stack, source_req_ids, requirement_lookup
        )

        prompt_text = _build_prompt_text(
            task_id=item["task_id"],
            domain_code=item["domain_code"],
            dispatch_mode=item["dispatch_mode"],
            agent_command=agent_command,
            source=source,
            score=score,
            subagent_type_hint=subagent_type_hint,
            requirement_block=requirement_block,
            solution_stack_block=solution_stack_block,
        )

        prompts.append(
            {
                "task_id": item["task_id"],
                "domain_code": item["domain_code"],
                "dispatch_mode": item["dispatch_mode"],
                "agent_command": agent_command,
                "subagent_type_hint": subagent_type_hint,
                "resolution_source": source,
                "source_req_ids": source_req_ids,
                "solution_stack": task_solution_stack,
                "prompt_text": prompt_text,
            }
        )
    return prompts
