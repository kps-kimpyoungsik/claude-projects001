"""[Phase 2 §6] 문서 전체 청크 경계 뷰(chunk-map) HTTP 어댑터.

`plans/_plan/02_PHASE2_ORCHESTRATION_PREVIEW.md` §6 설계 구현. §2 기존 `GET /requirements/
{req_id}/preview`(REQ 1건의 char 구간만 하이라이트)와 달리, 이 라우터는 **문서 1건 전체**와
그 문서에서 나온 **모든 REQ의 청크 경계**를 함께 반환한다 — gap(미청킹 구간)·overlap(겹침
구간) 계산은 프론트엔드(`documents.html`)가 이 목록만으로 렌더링 시점에 수행한다(§6-2,
백엔드는 정렬된 원자료만 제공 — 신규 계산 로직을 서버·클라이언트 양쪽에 중복 두지 않는다).

신규 저장소·신규 비즈니스 로직 없음(CRZ) — `RequirementStore.list_all()`로 걸러내고
`DocumentStore.load()`로 원문을 읽는다. envelope·에러코드·PII 클릭스루 게이트는 기존
`requirements_api` 모듈의 함수를 그대로 재사용한다(신규 포맷/게이트 로직 발명 없음).
monkeypatch 테스트 격리(§DRL 패턴)를 그대로 따르기 위해 `requirements_api` 모듈 객체를
통해 `get_requirement_store()`/`get_document_store()`/`_append_preview_access_log()`를
호출한다(모듈 속성 조회 시점에 해석 — `from ... import name`으로 직접 바인딩하면
테스트의 monkeypatch.setattr(requirements_api, ...)가 이 모듈에는 반영되지 않는다).
"""

from dataclasses import asdict

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse

from backend.adapters.api import requirements_api
from backend.adapters.persistence.project_registry import DEFAULT_PROJECT_ID
from backend.application.services.document_upload_service import (
    NotImplementedUploadFormatError,
    UnsupportedUploadFormatError,
    process_uploaded_file,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    actor: str = Form(...),
    project_id: str = Form(DEFAULT_PROJECT_ID),
):
    """[2026-07-22 신규] 문서 업로드 → 파싱 → 청킹 → 분류·채번 실제 HTTP 엔드포인트.

    `document_upload_service.process_uploaded_file`이 지금까지 테스트에서만 직접
    호출되고 실제 라우트에 배선되지 않았던 갭을 메운다(§W-5 실측으로 2026-07-22 발견).
    신규 비즈니스 로직 없음(CRZ) — 기존 서비스 함수를 그대로 호출만 한다.
    """
    content = await file.read()
    if not content:
        return JSONResponse(
            status_code=422,
            content=requirements_api.error_envelope("AEGIS-VALIDATION", "빈 파일은 업로드할 수 없습니다"),
        )

    req_store = requirements_api.get_requirement_store(project_id)
    doc_store = requirements_api.get_document_store(project_id)

    try:
        result = process_uploaded_file(
            filename=file.filename or "unnamed",
            content=content,
            actor=actor,
            req_store=req_store,
            doc_store=doc_store,
        )
    except UnsupportedUploadFormatError as exc:
        return JSONResponse(status_code=422, content=requirements_api.error_envelope("AEGIS-VALIDATION", str(exc)))
    except NotImplementedUploadFormatError as exc:
        return JSONResponse(status_code=422, content=requirements_api.error_envelope("AEGIS-VALIDATION", str(exc)))
    except ValueError as exc:
        return JSONResponse(status_code=422, content=requirements_api.error_envelope("AEGIS-VALIDATION", str(exc)))

    # [2026-07-25 고도화] 업로드로 채번된 Requirement들도 수동 등록 경로(requirements_api.
    # create_requirement_manual)와 동일하게 그래프 동기화한다(CRZ — sync_requirement_to_graph
    # 재사용, 신규 동기화 로직 없음). 이 엔드포인트는 원래 req_store 쓰기 자체가 락으로
    # 보호되지 않는 기존 갭이 있으나(별도 이슈, 이번 범위 밖 — directive로 표면화 예정),
    # 그래프 파일만은 requirements_api._write_lock으로 감싸 read-modify-write 경합을 막는다.
    with requirements_api._write_lock:
        for created_record in result.requirements_created:
            requirements_api.sync_requirement_to_graph(created_record, project_id)

    return requirements_api.envelope(
        ok=True,
        data={
            "doc_id": result.doc_id,
            "doc_filename": result.doc_filename,
            "chunk_count": result.chunk_count,
            "requirements_created": [r.req_id for r in result.requirements_created],
            "unclassified_chunk_count": result.unclassified_chunk_count,
        },
    )


@router.get("/{doc_id}/chunk-map")
def chunk_map(
    doc_id: str,
    actor: str = Query(...),
    confirm_pii: bool = Query(False),
    project_id: str = Query(DEFAULT_PROJECT_ID),
):
    req_store = requirements_api.get_requirement_store(project_id)
    doc_store = requirements_api.get_document_store(project_id)

    content = doc_store.load(doc_id)
    if content is None:
        return JSONResponse(
            status_code=404,
            content=requirements_api.error_envelope("AEGIS-NOTFOUND", f"존재하지 않는 doc_id: {doc_id}"),
        )

    # 이 문서에서 나온 REQ만 걸러 char_start 오름차순 정렬(§6-2 — 렌더링이 이 순서를 그대로
    # 신뢰해 블록을 왼쪽부터 쌓는다).
    records = [r for r in req_store.list_all() if r.doc_id == doc_id]
    records.sort(key=lambda r: (r.char_start if r.char_start is not None else 0))

    # §2-4/§6-1 PII 게이트를 문서맵 진입 시점에도 동일하게 적용 — 이 문서에서 나온 REQ 중
    # 하나라도 PII로 판정되면 문서 전체를 가린다(개별 블록만 가리면 원문 텍스트 자체가 이미
    # 노출되므로 문서 단위 게이트가 맞다).
    any_pii = any(getattr(r, "contains_pii", False) for r in records)
    if any_pii and not confirm_pii:
        return requirements_api.envelope(ok=True, data={"doc_id": doc_id, "requires_pii_confirmation": True})

    if any_pii and confirm_pii:
        # req_id 필드에 doc_id를 기록 — 문서 단위 열람이라 개별 req_id가 없다(기존 로그
        # 포맷·저장소를 그대로 재사용하기 위한 의도적 선택, 신규 로그 스키마 발명 없음).
        requirements_api._append_preview_access_log(f"doc::{doc_id}", actor, project_id)

    chunks = [
        {
            "req_id": r.req_id,
            "char_start": r.char_start,
            "char_end": r.char_end,
            "area_code": r.area_code,
            "doc_type_code": r.doc_type_code,
            "heading_path": r.heading_path,
            "lifecycle_status": r.lifecycle_status,
        }
        for r in records
        if r.char_start is not None and r.char_end is not None
    ]

    return requirements_api.envelope(
        ok=True,
        data={
            "doc_id": doc_id,
            "content": content,
            "requires_pii_confirmation": False,
            "chunks": chunks,
        },
    )
