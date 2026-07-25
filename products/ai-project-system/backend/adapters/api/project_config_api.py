"""[2026-07-25 고도화] 프로젝트 설정(0차 마법사, project_config.json) 영속화 HTTP 어댑터.

배경(§8-9 검토에서 실측 발견): `ProjectConfigStore`/`ProjectConfig`는 기존부터 있었으나
어떤 API 라우터에도 연결돼 있지 않았다 — 마법사가 `POST /projects`로 프로젝트 이름만
서버에 만들고, STEP2~STEP3에서 고른 분야·HA·보안·인프라존 설정 전체는 브라우저
`downloadConfig()`로 로컬 다운로드하는 것 말고는 서버에 저장되지 않았다(회귀 아님 —
원래부터 없던 연결, 이번에 처음 배선).

`doc_types_api.py`/`requirements_api.py`와 동일한 얇은 라우터 패턴(CRZ) — 신규 저장
로직은 만들지 않고 기존 `ProjectConfigStore`/`project_scope.resolve_project_data_dir()`를
그대로 재사용한다. 프로젝트별 격리도 기존 관례 그대로: `project_id` 쿼리 파라미터로
`data/(projects/{project_id}/)?project_config.json`에 저장.
"""

from dataclasses import asdict

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.adapters.api.requirements_api import envelope, error_envelope
from backend.adapters.persistence import project_scope
from backend.adapters.persistence.project_config_store import (
    ProjectConfig,
    ProjectConfigStore,
    ProjectConfigValidationError,
)
from backend.adapters.persistence.project_registry import DEFAULT_PROJECT_ID

router = APIRouter(prefix="/project-config", tags=["project-config"])


def get_project_config_store(project_id: str = DEFAULT_PROJECT_ID) -> ProjectConfigStore:
    return ProjectConfigStore(project_scope.resolve_project_data_dir(project_id) / "project_config.json")


class ProjectConfigRequest(BaseModel):
    """`ProjectConfig` dataclass와 1:1 대응(CRZ — 필드 목록은 그 파일이 SSOT).

    `created_by`/`created_at`/`project_design_draft_confirmed_by`/`_at`는 서버가
    저장 시점에 채우므로 클라이언트 입력에서 제외한다(기존 `ProjectConfigStore.save()`
    로직 그대로 — 신규 로직 없음).
    """

    project_name: str
    goal: str
    selected_areas: list[str] = Field(default_factory=list)
    selected_layers: list[str] = Field(default_factory=list)
    selected_doc_types: list[str] = Field(default_factory=list)
    solution_stack: list[str] = Field(default_factory=list)
    access_policy: str = "SHARED"
    project_design_draft_confirmed: bool = False
    is_ha: bool = False
    ha_management: str | None = None
    uses_websocket: bool = False
    realtime_backplane: str | None = None
    uses_grid: bool = False
    grid_solution: str | None = None
    grid_is_opensource: bool | None = None
    grid_guide_url: str | None = None
    has_ai_workload: bool = False
    llm_solution: str | None = None
    llm_server_info: str | None = None
    has_report: bool = False
    report_solution: str | None = None
    report_is_free: bool | None = None
    report_guide_url: str | None = None
    security_level: str = "standard"
    use_https: bool = False
    tls_cert_type: str | None = None
    password_hash_algo: str = "sha256"
    session_based_login: bool = True
    infra_configured: bool = False
    infra_zones: list[dict] = Field(default_factory=list)
    infra_servers: list[dict] = Field(default_factory=list)
    infra_allow_rules: list[dict] = Field(default_factory=list)
    enforce_https_external: bool = True
    relay_required: bool = True
    actor: str = Field(..., min_length=1)


@router.get("")
def get_project_config(project_id: str = Query(DEFAULT_PROJECT_ID)):
    store = get_project_config_store(project_id)
    config = store.load()
    if config is None:
        return envelope(ok=True, data={"config": None})
    return envelope(ok=True, data={"config": asdict(config)})


@router.put("")
def save_project_config(body: ProjectConfigRequest, project_id: str = Query(DEFAULT_PROJECT_ID)):
    fields = body.model_dump(exclude={"actor"})
    config = ProjectConfig(**fields)
    store = get_project_config_store(project_id)
    try:
        saved = store.save(config, created_by=body.actor)
    except ProjectConfigValidationError as exc:
        return JSONResponse(status_code=422, content=error_envelope("AEGIS-VALIDATION", str(exc)))
    return envelope(ok=True, data={"config": asdict(saved)})
