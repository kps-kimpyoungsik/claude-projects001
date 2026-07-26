"""요구사항 상태변경·미리보기 HTTP 어댑터 (얇은 라우터 — 신규 비즈니스 로직 없음).

`plans/_plan/07_API_SERVER_ARCHITECTURE.md` §4 설계 그대로 구현한다. `RequirementStore.
set_status()`·`DocumentStore.load()`는 이미 확정된 함수를 그대로 호출만 한다(CRZ).

동시성(§DRL-1): 이 프로세스 안에서 여러 요청이 동시에 들어와도 `RequirementStore`의
read-modify-write(JSON 전체 로드 → 수정 → 전체 저장)가 서로 겹치지 않도록 쓰기 경로
(상태 변경·PII 열람 로그 append)를 공유 락 하나로 직렬화한다.
`RequirementStore`/`DocumentStore` 자체는 수정하지 않는다(기존 클래스 계약 불변).
이 락은 "같은 프로세스 안의 스레드 경합"만 막는다 — 여러 프로세스(uvicorn --workers > 1)로
띄우면 이 락으로 막을 수 없으므로, 실행 가이드(§3)대로 반드시 단일 프로세스(--workers 지정
없이 기본값)로만 기동한다.

[2026-07-26 순수 이동] 이 락(`_write_lock`)과 그래프 경로 헬퍼(`_graph_path`)는 요구사항
도메인 전용이 아니라 여러 API 어댑터가 공유하는 범용 JSON 파일 스토어 동시성 관심사라
`backend/adapters/persistence/file_lock.py`로 소유권을 옮겼다(동작 변경 없음, CRZ) — 이
모듈은 그 정본을 재사용만 한다(하위 호환을 위해 동일 이름으로 재노출).
"""

import json
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.adapters.api.auth import require_api_key
from backend.adapters.persistence import project_scope
from backend.adapters.persistence.doc_type_registry import DocTypeRegistry
from backend.adapters.persistence.document_store import DocumentStore
from backend.adapters.persistence.file_lock import graph_path as _graph_path
from backend.adapters.persistence.file_lock import write_lock as _write_lock
from backend.adapters.persistence.project_config_store import ProjectConfigStore
from backend.adapters.persistence.project_registry import DEFAULT_PROJECT_ID
from backend.adapters.persistence.requirement_store import RequirementRecord, RequirementStore
from backend.adapters.persistence.task_store import TaskStore
from backend.application.services.graph_pipeline_service import merge_into_graph
from backend.domain.entities.task import InvalidDomainCodeError, Task
from backend.domain.graph.entities import Node, NodeKind
from backend.domain.requirements.classifier import ClassificationResult
from backend.domain.requirements.codes import DOMAIN_CODES, LAYER_CODES, REQUIREMENT_TYPES
from backend.domain.requirements.design_gate import evaluate_design_draft_gate

router = APIRouter(prefix="/requirements", tags=["requirements"], dependencies=[Depends(require_api_key)])

# §DRL-1 — 상태변경·PII 열람 로그 append를 직렬화하는 프로세스 내 단일 락.
# [2026-07-26] 정본은 `backend/adapters/persistence/file_lock.write_lock` — 위 import에서
# `_write_lock`이라는 기존 이름으로 재노출한다(하위 호환, 동일 객체 — 새 Lock() 아님).


def envelope(ok: bool, data: dict | None = None, error: dict | None = None) -> dict:
    """T99 AIOS 공통 응답 포맷 — `backend/adapters/api/health.py`의 `health_envelope()`과
    동일한 4키 구조를 재사용한다(신규 포맷 발명 없음)."""
    return {
        "ok": ok,
        "data": data,
        "error": error,
        "meta": {"degraded": False, "stub": False},
    }


def error_envelope(code: str, message: str, details: dict | None = None) -> dict:
    return envelope(ok=False, data=None, error={"code": code, "message": message, "details": details or {}})


class StatusChangeRequest(BaseModel):
    """§4-1 요청 바디 — Pydantic 자동 검증이 T99 AIOS 경계검증(malformed → 4xx)을
    별도 코드 없이 충족한다(§2-2 근거)."""

    status: str = Field(..., min_length=1)
    actor: str = Field(..., min_length=1)
    reason: str | None = None


class ManualRequirementCreateRequest(BaseModel):
    """[2026-07-23 고도화] "단건 요구사항 등록" — 사용자 지시("중간 애자일 방식 요구사항이
    들어올 수도 있고... 단건 등록 프롬프트가 될 수도 있어서")에 대한 실제 구현. 문서
    업로드·청킹 없이 사람이 바로 입력한 요구사항 1건을 등록한다 — 근거 코드(doc_type_code/
    area_code)는 사람이 직접 지정하므로 신뢰도 1.0·검토 불필요로 취급(자동분류가 아니라
    사람이 확정한 값이기 때문, classify_chunk()의 "애매하면 확신 없이" 원칙과 다른 축)."""

    description: str = Field(..., min_length=1)
    doc_type_code: str = Field(..., min_length=1)
    area_code: str = Field(..., min_length=1)
    actor: str = Field(..., min_length=1)
    layer_code: str | None = None
    requirement_type: str | None = None


class RechunkRequest(BaseModel):
    """02_PHASE2_ORCHESTRATION_PREVIEW.md §5-2 — "재청킹 요청" 액션 요청 바디.
    reason은 필수(추정 사유 금지, §5-2·set_status()의 REJECTED reason 필수 규칙과 정합)."""

    actor: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    suggested_char_start: int | None = None
    suggested_char_end: int | None = None


def get_requirement_store(project_id: str = DEFAULT_PROJECT_ID) -> RequirementStore:
    """스토어 경로 — §9에서 미확정으로 남겼던 항목. 이번 구현 사이클에서 프로젝트 루트
    `data/requirements_store.json`을 기본값으로 선택한다(실제 수집 파이프라인이 아직 없어
    확정된 값이 아니라는 점을 그대로 밝혀둔다 — T98 AIP, 추후 배선 시 이 함수만 바꾸면 됨).

    [2026-07-22 고도화] `project_id` 파라미터 추가 — 여러 프로젝트를 한 인스턴스에서
    관리하기 위해 `project_scope.resolve_project_data_dir()`로 프로젝트별 디렉터리를
    격리한다. 기본값(`DEFAULT_PROJECT_ID`)은 기존 평면 경로 그대로라 무마이그레이션."""
    return RequirementStore(project_scope.resolve_project_data_dir(project_id) / "requirements_store.json")


def get_project_config_store_for_gate(project_id: str = DEFAULT_PROJECT_ID) -> ProjectConfigStore:
    """[2026-07-25 §8-9 D-24d7a5fd] `list_requirements()`가 STEP6 시안게이트 판정에 필요한
    `project_design_draft_confirmed`를 읽기 위한 팩토리 — `get_requirement_store()`와 동일
    패턴(project_scope 재사용, CRZ). 별도 팩토리로 분리해 테스트에서 monkeypatch 가능하게
    한다(`get_requirement_store`/`get_document_store`와 같은 격리 관례, T53 VIP 회귀수정)."""
    return ProjectConfigStore(project_scope.resolve_project_data_dir(project_id) / "project_config.json")


def _get_task_store_for_generation(project_id: str) -> TaskStore:
    """[2026-07-23 신규] `tasks_api.get_task_store()`와 동일한 경로 결정(project_scope
    재사용, CRZ — 새 경로규칙 발명 없음)을 이 파일에서 독립적으로 구성한다. tasks_api가
    이미 `requirements_api.envelope/error_envelope`를 import하고 있어(§역방향금지),
    반대방향 import(requirements_api → tasks_api)는 순환 import를 만든다 — 그래서
    TaskStore만 직접 조립한다."""
    return TaskStore(project_scope.resolve_project_data_dir(project_id) / "tasks_store.json")


def get_document_store(project_id: str = DEFAULT_PROJECT_ID) -> DocumentStore:
    """§DRL-2 — 원문 저장 위치. `GET /requirements/{req_id}/preview`가 유일한 접근 경로가
    되도록(§6) 이 디렉터리는 `frontend/`(StaticFiles 마운트 대상, §5) 밖에 둔다."""
    return DocumentStore(project_scope.resolve_project_data_dir(project_id) / "documents")


def _preview_access_log_path(project_id: str = DEFAULT_PROJECT_ID):
    return project_scope.resolve_project_data_dir(project_id) / "preview_access_log.jsonl"


# [2026-07-26] `_graph_path`의 정본은 `backend/adapters/persistence/file_lock.graph_path` —
# 위 import에서 기존 이름 `_graph_path`로 재노출한다(하위 호환, 로직 변경 없음). 5-agent
# 진단(2026-07-24)에서 확인된 "`.graphify-out/`가 항상 비어있다"의 직접 원인이 이 경로에
# 실제로 쓰는 호출부 부재였다는 배경은 그대로 유효하다 — `sync_requirement_to_graph()`가
# 요구사항이 채번될 때마다 이 경로에 노드를 동기화한다.


def sync_requirement_to_graph(record: RequirementRecord, project_id: str = DEFAULT_PROJECT_ID) -> None:
    """[2026-07-25 고도화] Requirement 1건을 그래프 Requirement 노드로 동기화.

    `tasks_api.py`가 `TaskStore.create_or_update(task, graph=...)`에 그래프를 배선하려면
    이 동기화가 **먼저** 있어야 한다 — 5-agent 진단에서 dev000이 재확인한 대로, 동기화 없이
    배선만 하면 `verify_task_requirement_links()`가 모든 source_req_ids를 "그래프에 없음"으로
    판정해 전체 Task가 강제 DRAFT로 회귀한다(`plans/_plan/UPGRADE_PLAN_2026-07-24_5agent.md`
    "P1 #6" 심층분석 참조). `merge_into_graph()`의 기존 중복노드 거부 로직을 그대로
    재사용한다(CRZ, 신규 병합로직 없음)."""
    node = Node(
        node_id=record.req_id,
        kind=NodeKind.REQUIREMENT,
        label=(record.description[:80] if record.description else record.req_id),
        source_ref=record.source_ref or record.req_id,
    )
    merge_into_graph(_graph_path(project_id), nodes=[node], edges=[])


def _append_preview_access_log(req_id: str, actor: str, project_id: str = DEFAULT_PROJECT_ID) -> None:
    """§4-2 — PII 열람 확인 로그. 02_PHASE2 §2-4에서 이미 확정된 포맷 그대로 append."""
    log_path = _preview_access_log_path(project_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"req_id": req_id, "actor": actor, "ts": datetime.now(timezone.utc).isoformat(), "granted": True}
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


@router.get("")
def list_requirements(project_id: str = Query(DEFAULT_PROJECT_ID)):
    """06_AGENT_DISPATCH_REPORTING.md §10-4 — 목록 API. [2026-07-23 정리] 프론트
    (requirements.html/documents.html)는 이미 이 실시간 API로 전환 완료(2026-07-22) —
    과거 정적 `data/requirements.json` export 경로는 소비자가 없어 제거함(§W-5 실측
    재확인, CRZ). 기존 필드는 그대로, `assigned_agent_command`/`work_status`만 신규
    추가(§10-4 그대로)."""
    store = get_requirement_store(project_id)
    config_store = get_project_config_store_for_gate(project_id)
    config = config_store.load()
    project_confirmed = bool(config and config.project_design_draft_confirmed)
    records = [
        {
            "req_id": r.req_id,
            "doc_type_code": r.doc_type_code,
            "area_code": r.area_code,
            "layer_code": r.layer_code,
            "requirement_type": r.requirement_type,
            "description": r.description,
            "doc_type_confidence": r.doc_type_confidence,
            "area_confidence": r.area_confidence,
            "lifecycle_status": r.lifecycle_status,
            "source_ref": r.source_ref,
            "assigned_agent_command": r.assigned_agent_command,
            "work_status": r.work_status,
            "design_gate_status": evaluate_design_draft_gate(
                r.design_draft_gate, r.design_draft_gate_override, project_confirmed
            ),
        }
        for r in store.list_all()
    ]
    return envelope(ok=True, data={"requirements": records})


@router.post("")
def create_requirement_manual(body: ManualRequirementCreateRequest, project_id: str = Query(DEFAULT_PROJECT_ID)):
    """[2026-07-23 고도화] 문서 업로드 경유 없이 요구사항 1건을 직접 등록한다 — 애자일
    중간 유입 요구사항(회의 중 나온 요청 등)을 문서로 만들 필요 없이 즉시 채번한다."""
    doc_type_registry = DocTypeRegistry(project_scope.resolve_project_data_dir(project_id) / "doc_types_registry.json")
    known_doc_types = set(doc_type_registry.list_all_codes())
    if body.doc_type_code not in known_doc_types:
        return JSONResponse(
            status_code=422,
            content=error_envelope(
                "AEGIS-VALIDATION",
                f"미등록 문서유형코드 '{body.doc_type_code}' (허용: {sorted(known_doc_types)}, "
                f"POST /doc-types로 새 유형 추가 가능)",
            ),
        )
    if body.area_code not in DOMAIN_CODES:
        return JSONResponse(
            status_code=422,
            content=error_envelope("AEGIS-VALIDATION", f"미등록 영역코드 '{body.area_code}' (허용: {sorted(DOMAIN_CODES)})"),
        )
    if body.layer_code is not None and body.layer_code not in LAYER_CODES:
        return JSONResponse(
            status_code=422,
            content=error_envelope("AEGIS-VALIDATION", f"미등록 계층코드 '{body.layer_code}' (허용: {sorted(LAYER_CODES)})"),
        )
    if body.requirement_type is not None and body.requirement_type not in REQUIREMENT_TYPES:
        return JSONResponse(
            status_code=422,
            content=error_envelope("AEGIS-VALIDATION", f"미등록 요구사항유형 '{body.requirement_type}' (허용: {sorted(REQUIREMENT_TYPES)})"),
        )

    classification = ClassificationResult(
        doc_type_code=body.doc_type_code,
        doc_type_confidence=1.0,
        area_code=body.area_code,
        area_confidence=1.0,
        layer_code=body.layer_code,
        requirement_type=body.requirement_type,
        needs_review=False,
    )
    store = get_requirement_store(project_id)
    with _write_lock:
        record = store.add_from_classification(
            classification,
            description=body.description,
            source_ref=f"manual::{body.actor}",
            extra_doc_types=known_doc_types,
        )
        sync_requirement_to_graph(record, project_id)
    return envelope(ok=True, data=asdict(record))


@router.get("/{req_id}")
def get_requirement(req_id: str, project_id: str = Query(DEFAULT_PROJECT_ID)):
    """§10-4 — 단건 조회. 기존 필드 전부 + `assigned_agent_command`/`work_status` 포함."""
    store = get_requirement_store(project_id)
    records = {r.req_id: r for r in store.list_all()}
    record = records.get(req_id)
    if record is None:
        return JSONResponse(status_code=404, content=error_envelope("AEGIS-NOTFOUND", f"존재하지 않는 req_id: {req_id}"))
    return envelope(ok=True, data=asdict(record))


@router.post("/{req_id}/generate-task")
def generate_task_from_requirement(req_id: str, project_id: str = Query(DEFAULT_PROJECT_ID)):
    """[2026-07-23 신규] REQ → Task 뼈대 생성 — 실측 기능흐름 검토(RTM 추적성 검토)에서
    발견된 Critical 갭("REQ 채번까지는 자동, Task 생성은 100% 수동")을 메운다
    (00_PROJECT_CONSTITUTION.md §3 "요구사항 근거 AI 태스크 생성" 고리).

    뼈대만 만든다(§PFE 뼈대→점진확장) — acceptance_criteria/impact_scope/solution_stack이
    비어 있으면 `TaskStore.create_or_update()`가 스스로 needs_escalation=True +
    status="DRAFT"로 묶어 "아직 실행 불가, 구체화 필요"임을 표시한다(자동생성=즉시실행가능
    이라고 과장하지 않음, T98 AIP). REJECTED/WITHDRAWN 요구사항은 생성 거부.

    이미 이 req_id를 참조하는 Task가 있으면 중복 생성하지 않고 기존 Task를 그대로
    반환한다(재호출 안전 — idempotent).
    """
    req_store = get_requirement_store(project_id)
    records = {r.req_id: r for r in req_store.list_all()}
    record = records.get(req_id)
    if record is None:
        return JSONResponse(status_code=404, content=error_envelope("AEGIS-NOTFOUND", f"존재하지 않는 req_id: {req_id}"))
    if record.lifecycle_status in ("REJECTED", "WITHDRAWN"):
        return JSONResponse(
            status_code=422,
            content=error_envelope(
                "AEGIS-VALIDATION",
                f"{req_id}: lifecycle_status={record.lifecycle_status} 요구사항은 태스크를 생성할 수 없음",
            ),
        )

    task_store = _get_task_store_for_generation(project_id)
    with _write_lock:
        for existing in task_store.list_all():
            if req_id in existing.source_req_ids:
                return envelope(ok=True, data={**asdict(existing), "already_existed": True})

        try:
            task_id = task_store.generate_task_id(record.area_code)
            task = Task(
                task_id=task_id,
                domain_code=record.area_code,
                title=record.description[:80],
                description=record.description,
                source_req_ids=[req_id],
                solution_stack=list(record.solution_stack),
            )
        except InvalidDomainCodeError as exc:
            return JSONResponse(status_code=422, content=error_envelope("AEGIS-VALIDATION", str(exc)))
        created = task_store.create_or_update(task)

    return envelope(ok=True, data={**asdict(created), "already_existed": False})


@router.post("/{req_id}/rechunk")
def request_rechunk(req_id: str, body: RechunkRequest, project_id: str = Query(DEFAULT_PROJECT_ID)):
    """02_PHASE2_ORCHESTRATION_PREVIEW.md §5-2 — "재청킹 요청" 액션.
    `POST .../status`와 동일한 T99 AIOS envelope + 락 패턴(§DRL-1)을 그대로 재사용한다."""
    store = get_requirement_store(project_id)
    with _write_lock:
        try:
            record = store.request_rechunk(
                req_id,
                actor=body.actor,
                reason=body.reason,
                suggested_char_start=body.suggested_char_start,
                suggested_char_end=body.suggested_char_end,
            )
        except KeyError:
            return JSONResponse(status_code=404, content=error_envelope("AEGIS-NOTFOUND", f"존재하지 않는 req_id: {req_id}"))
        except ValueError as exc:
            return JSONResponse(status_code=422, content=error_envelope("AEGIS-VALIDATION", str(exc)))

    return envelope(
        ok=True,
        data={
            "req_id": record.req_id,
            "lifecycle_status": record.lifecycle_status,
            "status_history": record.status_history,
        },
    )


@router.post("/{req_id}/status")
def change_status(req_id: str, body: StatusChangeRequest, project_id: str = Query(DEFAULT_PROJECT_ID)):
    store = get_requirement_store(project_id)
    with _write_lock:
        try:
            record = store.set_status(req_id, body.status, actor=body.actor, reason=body.reason)
        except KeyError:
            return JSONResponse(status_code=404, content=error_envelope("AEGIS-NOTFOUND", f"존재하지 않는 req_id: {req_id}"))
        except ValueError as exc:
            return JSONResponse(status_code=422, content=error_envelope("AEGIS-VALIDATION", str(exc)))

    return envelope(
        ok=True,
        data={
            "req_id": record.req_id,
            "lifecycle_status": record.lifecycle_status,
            "status_history": record.status_history,
        },
    )


@router.get("/{req_id}/preview")
def preview(
    req_id: str,
    actor: str = Query(...),
    confirm_pii: bool = Query(False),
    project_id: str = Query(DEFAULT_PROJECT_ID),
):
    store = get_requirement_store(project_id)
    records = {r.req_id: r for r in store.list_all()}
    record = records.get(req_id)
    if record is None:
        return JSONResponse(status_code=404, content=error_envelope("AEGIS-NOTFOUND", f"존재하지 않는 req_id: {req_id}"))

    # §DRL-2 — RequirementRecord.contains_pii는 이제 실제 필드다(backend.domain.requirements.
    # pii_detector.scan_for_pii()가 add_from_classification() 시점에 채운다, 2026-07-19).
    # getattr 기본값 폴백은 이 필드가 없던 구버전 스토어 파일(과거 데이터)과의 호환을 위해
    # 그대로 유지한다 — 신규 레코드는 항상 실제 값을 갖는다.
    contains_pii = getattr(record, "contains_pii", False)
    if contains_pii and not confirm_pii:
        return envelope(ok=True, data={"requires_pii_confirmation": True, "req_id": req_id})

    if contains_pii and confirm_pii:
        with _write_lock:
            _append_preview_access_log(req_id, actor, project_id)

    doc_store = get_document_store(project_id)
    content = doc_store.load(record.doc_id) if record.doc_id else None
    excerpt = None
    if content is not None and record.char_start is not None and record.char_end is not None:
        excerpt = content[record.char_start:record.char_end]

    return envelope(
        ok=True,
        data={
            "req_id": record.req_id,
            "doc_id": record.doc_id,
            # §DRL-2 — RequirementRecord.doc_filename이 이제 저장 시점에 채워진다(레코드가
            # 유일한 근거). 구버전 스토어 파일(필드 없음)과의 호환을 위해 getattr 기본값으로
            # 그 자리에서 유도하는 기존 로직을 폴백으로 유지한다.
            "doc_filename": getattr(record, "doc_filename", None) or (f"{record.doc_id}.md" if record.doc_id else None),
            "heading_path": record.heading_path,
            "char_start": record.char_start,
            "char_end": record.char_end,
            "content_excerpt": excerpt,
            "contains_pii": contains_pii,
            "doc_type_confidence": record.doc_type_confidence,
            "area_confidence": record.area_confidence,
        },
    )
