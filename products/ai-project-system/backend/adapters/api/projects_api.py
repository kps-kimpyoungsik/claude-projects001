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
from pydantic import BaseModel, Field, ValidationError

from backend.adapters.api import project_config_api, tasks_api
from backend.adapters.api.requirements_api import envelope, error_envelope
from backend.adapters.persistence.file_lock import write_lock as _write_lock
from backend.adapters.persistence.project_registry import ProjectRegistry, ProjectValidationError
from backend.application.services.project_consistency_check import find_orphans
from backend.application.services.project_creation_service import (
    ProjectCreationError,
    create_project_atomic,
)

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(require_api_key)])

_REGISTRY_PATH = Path("data") / "projects_registry.json"


def get_project_registry() -> ProjectRegistry:
    return ProjectRegistry(_REGISTRY_PATH)


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    start_date: str | None = None
    end_date: str | None = None
    # [2026-07-27 신설] 원자적 생성 — `config`가 함께 오면 `ProjectConfig`(project_config_api.
    # ProjectConfigRequest와 동일 필드셋)까지 같은 요청에서 저장한다. 생략하면 기존 계약
    # (레지스트리 엔트리만 생성) 그대로 동작 — 하위호환 유지(CRZ, 기존 `POST /projects`
    # 단독 호출 소비자를 깨지 않음).
    config: dict | None = None
    actor: str | None = None


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
    """[2026-07-26 회귀수정] 전체 파일 read-modify-write인데 락이 없어 동시 생성 시 레코드
    유실 가능(실측 발견) — file_lock.write_lock 재사용(CRZ).

    [2026-07-27 고도화] `config`가 함께 오면 registry 생성 + `ProjectConfig` 저장을
    `project_creation_service.create_project_atomic()`으로 원자적으로 묶는다 — config 저장이
    실패하면 방금 만든 registry 레코드를 롤백해 "설정 없는 고아 프로젝트"가 생기지 않는다.
    `config`를 생략하면 기존 계약(레지스트리 엔트리만 생성) 그대로 동작(하위호환, CRZ)."""
    registry = get_project_registry()
    with _write_lock:
        if body.config is None:
            try:
                project = registry.create(body.name, start_date=body.start_date, end_date=body.end_date)
            except ProjectValidationError as exc:
                return JSONResponse(status_code=422, content=error_envelope("AEGIS-VALIDATION", str(exc)))
            return envelope(ok=True, data=_to_dict(project))

        try:
            # project_config_api.ProjectConfigRequest를 재사용해 필드 검증(area/layer/doc_type
            # 코드·보안레벨·인프라존 등)까지 그대로 상속한다(CRZ — 검증 로직 중복 금지). config
            # 안에 project_name/actor가 섞여 있어도 아래 명시 인자가 우선하도록 pop 처리.
            config_payload = dict(body.config)
            config_payload.pop("project_name", None)
            config_payload.pop("actor", None)
            validated_config = project_config_api.ProjectConfigRequest(
                project_name=body.name,
                actor=body.actor or "guest",
                **config_payload,
            )
        except ValidationError as exc:
            return JSONResponse(status_code=422, content=error_envelope("AEGIS-VALIDATION", str(exc)))

        try:
            project, _saved_config = create_project_atomic(
                registry,
                project_config_api.get_project_config_store,
                name=body.name,
                start_date=body.start_date,
                end_date=body.end_date,
                config_fields=validated_config.model_dump(exclude={"actor"}),
                actor=validated_config.actor,
            )
        except ProjectValidationError as exc:
            return JSONResponse(status_code=422, content=error_envelope("AEGIS-VALIDATION", str(exc)))
        except ProjectCreationError as exc:
            return JSONResponse(status_code=422, content=error_envelope("AEGIS-VALIDATION", str(exc)))

    return envelope(ok=True, data=_to_dict(project))


@router.get("/_consistency-check")
def consistency_check():
    """[2026-07-27 신설] 기존 데이터에서 고아(project↔config 불일치) 실측 탐지 — **자동
    삭제·자동 수정 없음**(발견·보고만, 사용자가 직접 판단). `/{project_id}` 파라미터
    라우트보다 먼저 등록해야 `_consistency-check`가 project_id로 오인되지 않는다(FastAPI는
    등록 순서대로 매칭)."""
    registry = get_project_registry()
    result = find_orphans(registry, project_config_api.get_project_config_store)
    return envelope(ok=True, data=result)


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
