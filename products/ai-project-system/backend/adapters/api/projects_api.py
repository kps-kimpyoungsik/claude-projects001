"""[2026-07-22 고도화] 프로젝트 목록·생성 HTTP 어댑터 — "여러 프로젝트 안에서 애자일
요구사항을 관리" 요청의 실제 진입점.

`requirements_api.py`의 envelope·에러코드 패턴을 그대로 재사용한다(CRZ, 신규 포맷 발명
없음). 신규 비즈니스 로직은 `ProjectRegistry`(project_registry.py) 하나뿐 — 이 라우터는
그 위에 얇게 HTTP를 씌운다.

[2026-07-26 고도화] 대시보드/편집화면(별도 트랙, frontend 미포함) 계약:
- `GET /projects/{project_id}` — 레지스트리 레코드 + `ProjectConfig`(goal/solution_stack 등)
  + 진행률을 병합한 상세 조회. 편집 폼 프리필용.
- `PATCH /projects/{project_id}` — 레지스트리 쪽 `name`/`start_date`/`end_date`만 갱신
  (설정 값은 기존 `PUT /project-config`가 전담 — 저장소 분리는 이번 범위 밖, CRZ).
- `GET /projects/{project_id}/progress` — `TaskStore`를 `analytics_api.py`와 동일한
  방식으로 재사용해 DONE/전체 태스크 비율을 계산.
"""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.adapters.api.auth import require_api_key
from pydantic import BaseModel, Field

from backend.adapters.api import project_config_api, tasks_api
from backend.adapters.api.requirements_api import envelope, error_envelope
from backend.adapters.persistence.file_lock import write_lock as _write_lock
from backend.adapters.persistence.project_registry import ProjectRegistry, ProjectValidationError

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(require_api_key)])

_REGISTRY_PATH = Path("data") / "projects_registry.json"


def get_project_registry() -> ProjectRegistry:
    return ProjectRegistry(_REGISTRY_PATH)


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    start_date: str | None = None
    end_date: str | None = None


class ProjectStatusUpdateRequest(BaseModel):
    status: str = Field(..., min_length=1)


class ProjectUpdateRequest(BaseModel):
    """`PATCH /projects/{project_id}` 요청 바디 — 세 필드 모두 선택(보내지 않은 필드는
    유지). `start_date`/`end_date`는 명시적으로 `null`을 보내면 지운다(레지스트리의
    `update_fields()` sentinel 계약과 동일 — pydantic이 "필드 미포함"과 "null 전송"을
    `exclude_unset`으로 구분해준다)."""

    name: str | None = None
    start_date: str | None = None
    end_date: str | None = None


def _to_dict(project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "status": project.status,
        "created_at": project.created_at.isoformat(),
        "start_date": project.start_date,
        "end_date": project.end_date,
    }


def _compute_progress(project_id: str) -> dict:
    """`analytics_api.failure_patterns()`와 동일 패턴(CRZ) — `tasks_api` 모듈을 통째로
    import해 `.get_task_store()`를 호출한다(테스트 monkeypatch가 원본 모듈 속성을
    패치해도 이 파일이 이미 캡처한 함수 참조가 아니라 매번 모듈에서 다시 조회하도록)."""
    task_store = tasks_api.get_task_store(project_id)
    tasks = task_store.list_all()
    total = len(tasks)
    done = sum(1 for t in tasks if t.status == "DONE")
    progress_pct = round((done / total) * 100, 1) if total else 0.0
    return {"done_tasks": done, "total_tasks": total, "progress_pct": progress_pct}


@router.get("")
def list_projects():
    registry = get_project_registry()
    return envelope(ok=True, data={"projects": [_to_dict(p) for p in registry.list_all()]})


@router.post("")
def create_project(body: ProjectCreateRequest):
    registry = get_project_registry()
    # [2026-07-26 회귀수정] 전체 파일 read-modify-write인데 락이 없어 동시 생성 시
    # 레코드 유실 가능(실측 발견) — file_lock.write_lock 재사용(CRZ).
    with _write_lock:
        try:
            project = registry.create(body.name, start_date=body.start_date, end_date=body.end_date)
        except ProjectValidationError as exc:
            return JSONResponse(status_code=422, content=error_envelope("AEGIS-VALIDATION", str(exc)))
    return envelope(ok=True, data=_to_dict(project))


@router.get("/{project_id}")
def get_project_detail(project_id: str):
    """[2026-07-26 신설] 레지스트리 레코드 + `ProjectConfig` + 진행률 병합 상세 조회 —
    편집화면(별도 트랙)이 폼을 프리필할 때 호출할 단일 엔드포인트."""
    registry = get_project_registry()
    project = registry.get(project_id)
    if project is None:
        return JSONResponse(
            status_code=404,
            content=error_envelope("AEGIS-NOTFOUND", f"존재하지 않는 프로젝트입니다: {project_id}"),
        )

    config_store = project_config_api.get_project_config_store(project_id)
    config = config_store.load()

    data = _to_dict(project)
    data["progress"] = _compute_progress(project_id)
    data["config"] = None
    if config is not None:
        data["config"] = {
            "goal": config.goal,
            "selected_areas": config.selected_areas,
            "selected_layers": config.selected_layers,
            "selected_doc_types": config.selected_doc_types,
            "solution_stack": config.solution_stack,
            "access_policy": config.access_policy,
        }
    return envelope(ok=True, data=data)


@router.patch("/{project_id}/status")
def update_project_status(project_id: str, body: ProjectStatusUpdateRequest):
    # 지금까지 프로젝트는 생성 후 status가 "IMPLEMENTING"에 고정돼 바꿀 방법이 없었다
    # (2026-07-23 고도화 후속 — ProjectRegistry.update_status() 신설에 맞춘 엔드포인트).
    registry = get_project_registry()
    with _write_lock:
        try:
            project = registry.update_status(project_id, body.status)
        except ProjectValidationError as exc:
            return JSONResponse(status_code=422, content=error_envelope("AEGIS-VALIDATION", str(exc)))
    return envelope(ok=True, data=_to_dict(project))


@router.patch("/{project_id}")
def update_project_fields(project_id: str, body: ProjectUpdateRequest):
    """[2026-07-26 신설] `name`/`start_date`/`end_date` 부분 업데이트 — `status`는
    위의 전용 엔드포인트가, 분야·목표 등 설정값은 `PUT /project-config`가 전담한다
    (두 저장소 분리 구조는 이번 범위 밖, CRZ — 이미 investigation에서 별도 아키텍처
    질문으로 플래그됨)."""
    registry = get_project_registry()
    payload = body.model_dump(exclude_unset=True)
    start_date = payload["start_date"] if "start_date" in payload else ...
    end_date = payload["end_date"] if "end_date" in payload else ...
    with _write_lock:
        try:
            project = registry.update_fields(
                project_id,
                name=payload.get("name"),
                start_date=start_date,
                end_date=end_date,
            )
        except ProjectValidationError as exc:
            return JSONResponse(status_code=422, content=error_envelope("AEGIS-VALIDATION", str(exc)))
    return envelope(ok=True, data=_to_dict(project))


@router.get("/{project_id}/progress")
def get_project_progress(project_id: str):
    """[2026-07-26 신설] `TaskStore.list_all()`을 세어 DONE 비율을 계산한다 —
    `analytics_api.py`가 이미 쓰는 로딩 방식 그대로 재사용(CRZ, 신규 로딩 메커니즘 없음)."""
    registry = get_project_registry()
    if registry.get(project_id) is None:
        return JSONResponse(
            status_code=404,
            content=error_envelope("AEGIS-NOTFOUND", f"존재하지 않는 프로젝트입니다: {project_id}"),
        )
    return envelope(ok=True, data=_compute_progress(project_id))
