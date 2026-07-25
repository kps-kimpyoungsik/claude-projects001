"""[2026-07-23 고도화] 프로젝트 배경 문서유형 동적 추가 HTTP 어댑터.

`projects_api.py`와 동일한 얇은 라우터 패턴(CRZ) — 신규 비즈니스 로직은
`DocTypeRegistry`(doc_type_registry.py) 하나뿐이다. 프로젝트별 격리는 기존 `project_scope.
resolve_project_data_dir()`를 그대로 재사용(신규 경로 규칙 발명 없음).
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.adapters.api.auth import require_api_key
from backend.adapters.api.requirements_api import envelope, error_envelope
from backend.adapters.persistence import project_scope
from backend.adapters.persistence.doc_type_registry import DocTypeRegistry, DocTypeValidationError
from backend.adapters.persistence.project_registry import DEFAULT_PROJECT_ID

router = APIRouter(prefix="/doc-types", tags=["doc-types"], dependencies=[Depends(require_api_key)])


def get_doc_type_registry(project_id: str = DEFAULT_PROJECT_ID) -> DocTypeRegistry:
    return DocTypeRegistry(project_scope.resolve_project_data_dir(project_id) / "doc_types_registry.json")


class DocTypeCreateRequest(BaseModel):
    label: str = Field(..., min_length=1)
    actor: str = Field(..., min_length=1)
    code: str | None = None


@router.get("")
def list_doc_types(project_id: str = Query(DEFAULT_PROJECT_ID)):
    registry = get_doc_type_registry(project_id)
    codes = registry.list_all_codes()
    custom_codes = {c.code for c in registry.list_custom()}
    return envelope(
        ok=True,
        data={
            "doc_types": [
                {"code": code, "label": label, "custom": code in custom_codes}
                for code, label in sorted(codes.items())
            ]
        },
    )


@router.post("")
def create_doc_type(body: DocTypeCreateRequest, project_id: str = Query(DEFAULT_PROJECT_ID)):
    registry = get_doc_type_registry(project_id)
    try:
        created = registry.create(body.label, actor=body.actor, code=body.code)
    except DocTypeValidationError as exc:
        return JSONResponse(status_code=422, content=error_envelope("AEGIS-VALIDATION", str(exc)))
    return envelope(ok=True, data={"code": created.code, "label": created.label, "custom": True})
