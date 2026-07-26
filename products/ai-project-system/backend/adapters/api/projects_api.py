"""[2026-07-22 고도화] 프로젝트 목록·생성 HTTP 어댑터 — "여러 프로젝트 안에서 애자일
요구사항을 관리" 요청의 실제 진입점.

`requirements_api.py`의 envelope·에러코드 패턴을 그대로 재사용한다(CRZ, 신규 포맷 발명
없음). 신규 비즈니스 로직은 `ProjectRegistry`(project_registry.py) 하나뿐 — 이 라우터는
그 위에 얇게 HTTP를 씌운다.
"""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.adapters.api.auth import require_api_key
from pydantic import BaseModel, Field

from backend.adapters.api.requirements_api import envelope, error_envelope
from backend.adapters.persistence.file_lock import write_lock as _write_lock
from backend.adapters.persistence.project_registry import ProjectRegistry, ProjectValidationError

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(require_api_key)])

_REGISTRY_PATH = Path("data") / "projects_registry.json"


def get_project_registry() -> ProjectRegistry:
    return ProjectRegistry(_REGISTRY_PATH)


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)


class ProjectStatusUpdateRequest(BaseModel):
    status: str = Field(..., min_length=1)


def _to_dict(project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "status": project.status,
        "created_at": project.created_at.isoformat(),
    }


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
            project = registry.create(body.name)
        except ProjectValidationError as exc:
            return JSONResponse(status_code=422, content=error_envelope("AEGIS-VALIDATION", str(exc)))
    return envelope(ok=True, data=_to_dict(project))


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
