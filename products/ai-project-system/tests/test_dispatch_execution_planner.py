"""dispatch_execution_planner — 배차 계획(dispatch_tasks 출력)을 실행 프롬프트 텍스트로
조립하는 순수 로직 검증. Agent() 호출을 하지 않는다는 것도 함께 확인(출력이 문자열/dict일 뿐).

2026-07-19 보강: plans/_plan/03_PHASE3_AGENT_GRAPHIFY.md §3-1 프롬프트 조립 공식 중
Requirement 원문 발췌 + solution_stack 병합 부분(requirement_lookup 주입) 회귀 테스트 추가."""

from backend.adapters.persistence.requirement_store import RequirementRecord
from backend.application.services.agent_dispatch_resolver import AgentResolution
from backend.application.services.dispatch_execution_planner import (
    build_execution_prompts,
)


def _plan_item(**overrides):
    defaults = dict(
        task_id="T1",
        domain_code="SEC",
        priority_score=0,
        dispatch_mode="parallel",
        agent_resolution=AgentResolution(
            domain_code="SEC",
            agent_command="/aegis-security",
            source="fallback_default",
            score=None,
            resolved_at="2026-07-19T00:00:00+00:00",
        ),
    )
    defaults.update(overrides)
    return defaults


def test_build_execution_prompts_returns_one_entry_per_plan_item():
    plan = [_plan_item(task_id="A"), _plan_item(task_id="B")]
    prompts = build_execution_prompts(plan)
    assert [p["task_id"] for p in prompts] == ["A", "B"]


def test_build_execution_prompts_carries_agent_command_and_hint():
    plan = [_plan_item(task_id="A")]
    prompts = build_execution_prompts(plan)
    entry = prompts[0]
    assert entry["agent_command"] == "/aegis-security"
    assert entry["subagent_type_hint"] == "aegis-security"
    assert entry["resolution_source"] == "fallback_default"
    assert "/aegis-security" in entry["prompt_text"]
    assert "Agent(subagent_type=\"aegis-security\"" in entry["prompt_text"]


def test_build_execution_prompts_sequential_mode_note_mentions_overlap():
    plan = [_plan_item(task_id="A", dispatch_mode="sequential")]
    entry = build_execution_prompts(plan)[0]
    assert "순차" in entry["prompt_text"]
    assert "PAW-3" in entry["prompt_text"]


def test_build_execution_prompts_parallel_mode_note_mentions_clear():
    plan = [_plan_item(task_id="A", dispatch_mode="parallel")]
    entry = build_execution_prompts(plan)[0]
    assert "병렬 배차 가능" in entry["prompt_text"]


def test_build_execution_prompts_handles_unresolved_agent_command():
    plan = [
        _plan_item(
            task_id="A",
            agent_resolution=AgentResolution(
                domain_code="ZZZ",
                agent_command=None,
                source="fallback_default",
                score=None,
                resolved_at="2026-07-19T00:00:00+00:00",
            ),
        )
    ]
    entry = build_execution_prompts(plan)[0]
    assert entry["agent_command"] is None
    assert entry["subagent_type_hint"] == "general-purpose"
    assert "미확정" in entry["prompt_text"]


def test_build_execution_prompts_accepts_dict_agent_resolution():
    """agent_resolution이 dataclass가 아니라 dict(JSON 왕복 등)로 와도 동일하게 동작해야 한다."""
    plan = [
        _plan_item(
            task_id="A",
            agent_resolution={
                "domain_code": "SEC",
                "agent_command": "/aegis-security",
                "source": "search_all",
                "score": 0.87,
                "resolved_at": "2026-07-19T00:00:00+00:00",
            },
        )
    ]
    entry = build_execution_prompts(plan)[0]
    assert entry["agent_command"] == "/aegis-security"
    assert entry["resolution_source"] == "search_all"
    assert "score=0.87" in entry["prompt_text"]


def test_build_execution_prompts_does_not_call_agent_tool():
    """이 함수는 문자열/기본 dict만 반환해야 한다 — Agent 호출 부작용이 없어야 한다."""
    plan = [_plan_item(task_id="A")]
    prompts = build_execution_prompts(plan)
    assert isinstance(prompts, list)
    assert all(isinstance(p, dict) for p in prompts)
    assert all(isinstance(p["prompt_text"], str) for p in prompts)


def test_build_execution_prompts_without_lookup_stays_backward_compatible():
    """requirement_lookup 미제공(하위호환) — source_req_ids가 있어도 크래시 없이
    "조회 함수 미제공"으로 정직하게 표시한다."""
    plan = [_plan_item(task_id="A", source_req_ids=["REQ-BIZ-SEC-001"])]
    entry = build_execution_prompts(plan)[0]
    assert "조회 함수 미제공" in entry["prompt_text"]
    assert entry["source_req_ids"] == ["REQ-BIZ-SEC-001"]


def _requirement(**overrides):
    defaults = dict(
        req_id="REQ-BIZ-SEC-001",
        doc_type_code="BIZ",
        area_code="SEC",
        description="결제 정보는 AES256으로 암호화해 저장해야 한다.",
        source_ref="doc::제안서.pdf",
        doc_type_confidence=0.9,
        area_confidence=0.9,
        heading_path=["3장 보안 요구사항", "3.2 저장 암호화"],
        char_start=120,
        char_end=180,
        solution_stack=["전자정부표준프레임워크"],
    )
    defaults.update(overrides)
    return RequirementRecord(**defaults)


def test_build_execution_prompts_includes_requirement_excerpt_and_source_location():
    req = _requirement()
    plan = [_plan_item(task_id="A", source_req_ids=["REQ-BIZ-SEC-001"])]

    entry = build_execution_prompts(
        plan, requirement_lookup=lambda req_id: req if req_id == req.req_id else None
    )[0]

    assert "AES256" in entry["prompt_text"]
    assert "doc::제안서.pdf" in entry["prompt_text"]
    assert "3장 보안 요구사항 > 3.2 저장 암호화" in entry["prompt_text"]
    assert "chars 120-180" in entry["prompt_text"]


def test_build_execution_prompts_merges_task_and_requirement_solution_stack():
    req = _requirement(solution_stack=["전자정부표준프레임워크", "FastAPI"])
    plan = [
        _plan_item(
            task_id="A",
            source_req_ids=["REQ-BIZ-SEC-001"],
            solution_stack=["FastAPI", "React"],
        )
    ]

    entry = build_execution_prompts(
        plan, requirement_lookup=lambda req_id: req if req_id == req.req_id else None
    )[0]

    # 중복(FastAPI)은 한 번만, 순서는 Task 것 먼저(FastAPI, React) + Requirement 신규분
    # (전자정부표준프레임워크)만 뒤에 추가.
    assert entry["prompt_text"].count("FastAPI") == 1
    assert "FastAPI, React, 전자정부표준프레임워크" in entry["prompt_text"]


def test_build_execution_prompts_reports_lookup_miss_without_crashing():
    """req_id가 스토어에 없으면(조회 실패) 크래시하지 않고 정직하게 "원문 조회 불가"로 표시."""
    plan = [_plan_item(task_id="A", source_req_ids=["REQ-BIZ-SEC-999"])]

    entry = build_execution_prompts(plan, requirement_lookup=lambda req_id: None)[0]

    assert "REQ-BIZ-SEC-999" in entry["prompt_text"]
    assert "원문 조회 불가" in entry["prompt_text"]


def test_build_execution_prompts_no_source_req_ids_shows_none_declared():
    plan = [_plan_item(task_id="A", source_req_ids=[])]
    entry = build_execution_prompts(plan, requirement_lookup=lambda req_id: None)[0]
    assert "source_req_ids 미지정" in entry["prompt_text"]
