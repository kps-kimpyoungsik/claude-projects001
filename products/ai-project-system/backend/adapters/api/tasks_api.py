"""[Phase 4.2] Task 상태 조회·전이 HTTP 어댑터 — 에이전트 통신 프로토콜의 실체.

00_DESIGN_TOC.md Phase 4.2("에이전트 통신 프로토콜(MCP) + 상태 머신")의 "통신 프로토콜" 축.
배차된 agent(또는 이를 대행하는 세션)가 Claude Code Agent 툴 내부에서 이 프로세스로 직접
MCP 호출을 하는 것은 아니다(그런 채널은 존재하지 않음, 과장 금지 T98 AIP) — 실제 통신 수단은
이 HTTP API다: 진행상황을 `POST /tasks/{task_id}/status`로 보고하면 `TaskStore.set_status()`가
전이 그래프(task_state_machine.py)로 검증 후 반영한다. `requirements_api.py`의 envelope·
에러코드·락 패턴을 그대로 재사용한다(CRZ, 신규 포맷 발명 없음).
"""

import json
import threading
from dataclasses import asdict

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.adapters.api.requirements_api import _graph_path, envelope, error_envelope
from backend.adapters.persistence import project_scope
from backend.adapters.persistence.project_registry import DEFAULT_PROJECT_ID
from backend.adapters.persistence.task_store import TaskStore
from backend.domain.entities.task import InvalidDomainCodeError, Task
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])

# §DRL-1 — requirements_api._write_lock과 동일 원칙(단일 프로세스 내 쓰기 직렬화).
_write_lock = threading.Lock()


class TaskCreateRequest(BaseModel):
    """[Phase 4.2 보완] `POST /tasks` 요청 바디 — 지금까지 `TaskStore.create_or_update()`가
    코드 레벨(테스트·다른 서비스)에서만 호출 가능했던 갭을 메운다. task_id는 서버가
    `TaskStore.generate_task_id()`로 채번한다(클라이언트가 임의 ID를 지정하지 않음 —
    RequirementStore가 REQ ID를 서버 채번하는 것과 동일 원칙, CRZ)."""

    domain_code: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    source_req_ids: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    impact_scope: list[str] = Field(default_factory=list)
    solution_stack: list[str] = Field(default_factory=list)


class TaskStatusChangeRequest(BaseModel):
    status: str = Field(..., min_length=1)
    actor: str = Field(..., min_length=1)
    reason: str | None = None
    # [Phase 5.3 HITL] 서킷 브레이커가 트립된 Task는 이 값을 True로 보내야만 전이 가능
    # (사람이 검토했음을 명시 — 자동/자율 세션이 임의로 True를 보내지 않도록 API 소비자
    # 쪽에서 실제 사람 확인 후에만 세팅하는 것을 전제로 한다, 강제 검증 코드는 없음).
    override_escalation: bool = False


def get_task_store(project_id: str = DEFAULT_PROJECT_ID) -> TaskStore:
    """스토어 경로 — requirements_api.get_requirement_store()와 동일 원칙으로
    `data/tasks_store.json`을 기본값으로 선택한다(실제 배차 파이프라인이 이 경로로
    아직 연결되지 않았다는 점을 그대로 밝혀둔다 — T98 AIP, 추후 배선 시 이 함수만 바꾸면 됨).

    [2026-07-22 고도화] `project_id` 추가 — requirements_api와 동일하게 `project_scope.
    resolve_project_data_dir()`로 프로젝트별 격리(CRZ, 동일 경로결정 로직 재사용)."""
    return TaskStore(project_scope.resolve_project_data_dir(project_id) / "tasks_store.json")


def _load_graph(project_id: str = DEFAULT_PROJECT_ID) -> dict | None:
    """[2026-07-25 고도화] Task 생성 시 요구사항 그래프 실재 검증(check_sufficiency의 graph
    인자)에 쓸 그래프를 읽는다. **파일이 없으면 반드시 `None`을 반환한다(빈 dict 아님)** —
    `requirements_api.sync_requirement_to_graph()`가 아직 이 프로젝트에서 한 번도 실행된
    적 없는 경우(그래프 파일 자체가 없음)까지 이 함수가 커버해야, `check_sufficiency()`가
    그 경우 그래프 검증을 건너뛰어(graph=None) 모든 source_req_ids를 "그래프에 없음"으로
    오판하는 회귀를 피한다(5-agent 진단 dev000 재확인 사항 — 빈 dict를 넘기면 100% 회귀)."""
    path = _graph_path(project_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("")
def list_tasks(project_id: str = Query(DEFAULT_PROJECT_ID)):
    store = get_task_store(project_id)
    tasks = [asdict(t) for t in store.list_all()]
    return envelope(ok=True, data={"tasks": tasks})


@router.post("")
def create_task(body: TaskCreateRequest, project_id: str = Query(DEFAULT_PROJECT_ID)):
    store = get_task_store(project_id)
    with _write_lock:
        try:
            task_id = store.generate_task_id(body.domain_code)
            task = Task(
                task_id=task_id,
                domain_code=body.domain_code,
                title=body.title,
                description=body.description,
                source_req_ids=list(body.source_req_ids),
                acceptance_criteria=list(body.acceptance_criteria),
                impact_scope=list(body.impact_scope),
                solution_stack=list(body.solution_stack),
            )
        except InvalidDomainCodeError as exc:
            return JSONResponse(status_code=422, content=error_envelope("AEGIS-VALIDATION", str(exc)))
        created = store.create_or_update(task, graph=_load_graph(project_id))

    return envelope(ok=True, data=asdict(created))


@router.get("/{task_id}")
def get_task(task_id: str, project_id: str = Query(DEFAULT_PROJECT_ID)):
    store = get_task_store(project_id)
    task = store.get(task_id)
    if task is None:
        return JSONResponse(status_code=404, content=error_envelope("AEGIS-NOTFOUND", f"존재하지 않는 task_id: {task_id}"))
    return envelope(ok=True, data=asdict(task))


@router.post("/{task_id}/status")
def change_task_status(task_id: str, body: TaskStatusChangeRequest, project_id: str = Query(DEFAULT_PROJECT_ID)):
    store = get_task_store(project_id)
    with _write_lock:
        try:
            task = store.set_status(
                task_id,
                body.status,
                actor=body.actor,
                reason=body.reason,
                override_escalation=body.override_escalation,
            )
        except KeyError:
            return JSONResponse(status_code=404, content=error_envelope("AEGIS-NOTFOUND", f"존재하지 않는 task_id: {task_id}"))
        except ValueError as exc:
            return JSONResponse(status_code=422, content=error_envelope("AEGIS-VALIDATION", str(exc)))

    return envelope(
        ok=True,
        data={
            "task_id": task.task_id,
            "status": task.status,
            "status_history": task.status_history,
            "needs_escalation": task.needs_escalation,
            "escalation_reasons": task.escalation_reasons,
        },
    )
