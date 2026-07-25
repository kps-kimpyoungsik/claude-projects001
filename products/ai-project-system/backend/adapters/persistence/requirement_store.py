"""[Phase 2 x Phase 3 연결] 분류된 요구사항 항목의 영속 저장소 + 채번.

backend.domain.classifier가 청크를 분류하면, 이 모듈이 REQ ID를 채번(requirements.py의
build_req_id 재사용)하고 항목을 JSON에 영속화한다. orchestrator/task_manager.py의
TaskStore와 동일한 "JSON 파일 기반 경량 저장소" 패턴을 그대로 따른다(CRZ — 새 저장 방식
발명 없음).

lifecycle_status가 "관리 포인트"다(plans/_plan/01_PHASE1_DATA_MODEL.md §2-3 — 2026-07-18
재설계로 status→lifecycle_status 확장, 9개 상태 + WITHDRAWN 소프트삭제). 분류기가 자신
없어 하면(needs_review=True) 사람이 확인하기 전까지 UNDER_REVIEW에 머문다. 사람이 확인한
결과는 이 스토어를 통해서만 ACCEPTED/REJECTED/WITHDRAWN으로 전이한다(자동 승격 없음 —
오분류 그대로 확정되는 것을 막는다). status_history(§2-3-A)가 "누가·언제·왜" 바꿨는지
전부 남긴다(철회사유·행위자기록 통합 감사로그 — 별도 필드로 중복 설계하지 않음, CRZ).
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from backend.application.ports.requirement_store_port import RequirementStorePort
from backend.domain.requirements.classifier import ClassificationResult
from backend.domain.requirements.codes import DESIGN_GATE_VALUES
from backend.domain.requirements.id_format import build_req_id
from backend.domain.requirements.pii_detector import scan_for_pii

# plans/_plan/01_PHASE1_DATA_MODEL.md §2-3 — 9개 라이프사이클 상태(기존 4값 status 대체).
LIFECYCLE_STATUSES = {
    "RECEIVED", "CLASSIFIED", "UNDER_REVIEW", "ACCEPTED",
    "IN_PROGRESS", "IMPLEMENTED", "VERIFIED", "REJECTED", "WITHDRAWN",
}
# §2-3-A — 이 상태로 전이할 때는 reason이 반드시 있어야 한다(추정 사유로 채우지 않음).
REASON_REQUIRED_STATUSES = {"WITHDRAWN", "REJECTED"}
# 06_AGENT_DISPATCH_REPORTING.md §10-2 — "코드 구현 진행" 축(lifecycle_status와 별개).
WORK_STATUSES = {"NOT_DISPATCHED", "DISPATCHED", "IN_PROGRESS", "DONE", "BLOCKED"}


@dataclass
class StatusChangeEvent:
    from_status: str
    to_status: str
    actor: str
    reason: str | None = None
    ts: str = ""


@dataclass
class RequirementRecord:
    req_id: str
    doc_type_code: str
    area_code: str
    description: str
    source_ref: str
    doc_type_confidence: float
    area_confidence: float
    layer_code: str | None = None
    layer_confidence: float = 0.0
    requirement_type: str | None = None
    requirement_type_confidence: float = 0.0
    solution_stack: list[str] = field(default_factory=list)
    matched_keywords: dict = field(default_factory=dict)
    lifecycle_status: str = "UNDER_REVIEW"
    status_history: list[dict] = field(default_factory=list)
    created_at: str = ""
    # plans/_plan/02_PHASE2_ORCHESTRATION_PREVIEW.md §1-2 — 미리보기가 원문을 찾아 하이라이트
    # 하기 위한 좌표(backend.domain.chunk.Chunk와 동일 필드, CRZ — 중복 정의 아니라 그대로 복사).
    doc_id: str = ""
    heading_path: list[str] = field(default_factory=list)
    char_start: int | None = None
    char_end: int | None = None
    # 사용자 요청("이미지가 있을 경우 이미지 분석을 통해 출처 감지") — 실제 이미지 OCR/비전
    # 분석은 아직 구현하지 않는다(ingestion/router.py의 vision_describe 전략 자체가 스텁,
    # T98 AIP 과장 금지). 이 두 필드는 그 미구현 상태를 화면에 정직하게 드러내는 용도.
    source_is_image: bool = False
    image_analysis_status: str = "not_applicable"  # "not_applicable" | "not_implemented"
    # plans/_plan/04_PHASE0_PROJECT_REGISTRATION.md §3 — 문서 접근제어(PII) 게이트 근거 필드.
    # backend.domain.requirements.pii_detector.scan_for_pii()가 add_from_classification()
    # 시점에 채운다(정규식/키워드 기반 결정론적 스캔, T98 AIP — LLM 의미판단 아님).
    contains_pii: bool = False
    pii_scan_matched: list[str] = field(default_factory=list)
    # requirements_api.py preview 응답의 doc_filename 유도 로직(§DRL-2)과 동일한 명명 규칙
    # (f"{doc_id}.md")을 저장 시점에 확정해둔다 — API 레이어가 매번 문자열을 조립하지 않고
    # 이 필드를 그대로 반환한다(레코드가 유일한 근거, CRZ — 유도 로직 중복 정의 금지).
    doc_filename: str | None = None
    # plans/_plan/01_PHASE1_DATA_MODEL.md §2-5~§2-7·§5-2 — 디자인 시안 선행 게이트(축 7).
    # design_draft_gate_confidence는 자동판정 신뢰도(§2-6), 수동 override 시 1.0 고정 원칙(§2-7).
    design_draft_gate: str | None = None
    design_draft_gate_confidence: float = 0.0
    design_draft_gate_history: list[dict] = field(default_factory=list)
    # §5-2 — 사람이 True로 지정하면 project_design_draft_confirmed 값과 무관하게 이 요구사항의
    # 게이트가 원래 규칙(§5-2-A) 그대로 작동한다.
    design_draft_gate_override: bool = False
    # plans/_plan/02_PHASE2_ORCHESTRATION_PREVIEW.md §5-2 — 재청킹으로 이 REQ를 대체한 새
    # req_id(신규, 2026-07-20). 원본은 WITHDRAWN 소프트삭제로 남고 이 필드는 새 REQ 쪽에
    # 채워 "무엇이 무엇을 대체했는지" 역방향으로 추적 가능하게 한다(물리 삭제 없음).
    supersedes_req_id: str | None = None
    # plans/_plan/06_AGENT_DISPATCH_REPORTING.md §10-2 — 배차 결과 되먹임(write-back) 필드.
    # lifecycle_status(사람의 승인 축)와 별개인 "코드 구현 진행" 축 — 신규 lifecycle 상태값을
    # 늘리지 않고 별도 축으로 분리한다(§10-1, CRZ).
    assigned_agent_command: str | None = None
    work_status: str = "NOT_DISPATCHED"
    work_status_updated_at: str = ""
    # 2026-07-22 (사용자 지시: "문서 안에서의 관계 판단도 해야 됩니다 / 출처가 확실해야
    # 됩니다") — SemanticBoundarySplitter(backend/domain/chunking/heading_splitter.py)가
    # LLM 판단으로 부착한 문서 내 관계. 각 항목은 to_chunk_id(대상 청크)·type·evidence(원문
    # 발췌, 출처)·confidence를 갖는다. judge 미가동 시 빈 리스트(과장 금지).
    related_chunks: list[dict] = field(default_factory=list)


class RequirementStore(RequirementStorePort):
    """`RequirementStorePort`의 JSON 파일 구현체.

    PostgreSQL 등으로 교체 시 이 클래스처럼 `RequirementStorePort`를 구현하는 새
    어댑터만 작성하면 되고, 호출부(`requirements_api.py`의 `get_requirement_store`)만
    바꾸면 된다 — Port 상속을 명시해 두면 향후 구현체가 계약을 놓치는 메서드를
    추상클래스 인스턴스화 시점에 즉시 잡아낸다.
    """

    def __init__(self, store_path: Path):
        self._path = store_path
        # 02_PHASE2_ORCHESTRATION_PREVIEW.md §5-2 — "재청킹 큐" ground-truth 이벤트 로그.
        # store_path와 같은 디렉터리에 둔다(requirements_api.py의 _PREVIEW_ACCESS_LOG와
        # 동일한 "스토어 파일 옆에 jsonl 로그" 배치 패턴, CRZ — 신규 경로 규칙 발명 없음).
        self._rechunk_queue_path = store_path.parent / "rechunk_queue.jsonl"

    def _load_all(self) -> dict:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _save_all(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _next_seq(self, data: dict, doc_type_code: str, area_code: str) -> int:
        """같은 (문서유형코드, 영역코드) 조합의 기존 최대 일련번호 + 1을 반환한다."""
        prefix = f"REQ-{doc_type_code}-{area_code}-"
        existing_seqs = [int(rid[len(prefix):]) for rid in data if rid.startswith(prefix)]
        return (max(existing_seqs) + 1) if existing_seqs else 1

    def add_from_classification(
        self, classification: ClassificationResult, description: str, source_ref: str,
        doc_id: str = "", heading_path: list | None = None,
        char_start: int | None = None, char_end: int | None = None,
        source_is_image: bool = False,
        related_chunks: list[dict] | None = None,
        extra_doc_types: set[str] | None = None,
    ) -> RequirementRecord | None:
        """분류 결과를 요구사항 항목으로 채번·저장한다.

        doc_type_code/area_code가 아예 없으면(둘 다 매칭 실패) 채번 자체를 하지 않는다 —
        "추정 요구사항 생성 금지" 원칙상 근거 코드가 없는 REQ ID는 만들 수 없다.

        doc_id·heading_path·char_start·char_end는 §1-2 위치정보 — 미리보기 화면이 원문에서
        정확히 이 구간을 하이라이트할 수 있게 한다. source_is_image=True면
        image_analysis_status="not_implemented"로 정직 표기(과장 금지).

        contains_pii/pii_scan_matched는 §3 — description(요구사항 본문 요약)을
        pii_detector.scan_for_pii()로 스캔해 채운다. 원문 전체가 아니라 description을
        스캔 대상으로 쓰는 이유: 이 함수가 받는 인자 중 원문 전체를 담고 있는 것은
        description뿐이고(source_ref는 위치 식별자일 뿐 본문이 아님), 미리보기 화면이
        실제로 노출하는 대상도 이 요구사항 항목 단위이기 때문이다.
        """
        if not classification.doc_type_code or not classification.area_code:
            return None

        data = self._load_all()
        seq = self._next_seq(data, classification.doc_type_code, classification.area_code)
        req_id = build_req_id(classification.doc_type_code, classification.area_code, seq, extra_doc_types=extra_doc_types)

        pii_result = scan_for_pii(description)

        record = RequirementRecord(
            req_id=req_id,
            doc_type_code=classification.doc_type_code,
            area_code=classification.area_code,
            description=description.strip()[:200],
            source_ref=source_ref,
            doc_type_confidence=classification.doc_type_confidence,
            area_confidence=classification.area_confidence,
            layer_code=classification.layer_code,
            layer_confidence=classification.layer_confidence,
            requirement_type=classification.requirement_type,
            requirement_type_confidence=classification.requirement_type_confidence,
            design_draft_gate=classification.design_draft_gate,
            design_draft_gate_confidence=classification.design_draft_gate_confidence,
            matched_keywords=classification.matched_keywords,
            lifecycle_status="UNDER_REVIEW" if classification.needs_review else "CLASSIFIED",
            created_at=datetime.now(timezone.utc).isoformat(),
            doc_id=doc_id,
            heading_path=heading_path or [],
            char_start=char_start,
            char_end=char_end,
            source_is_image=source_is_image,
            image_analysis_status="not_implemented" if source_is_image else "not_applicable",
            contains_pii=pii_result.contains_pii,
            pii_scan_matched=pii_result.pii_scan_matched,
            related_chunks=related_chunks or [],
            doc_filename=f"{doc_id}.md" if doc_id else None,
        )
        data[req_id] = asdict(record)
        self._save_all(data)
        return record

    def set_status(self, req_id: str, status: str, actor: str, reason: str | None = None) -> RequirementRecord:
        """사람이 확인한 결과를 반영한다 — ACCEPTED/REJECTED/WITHDRAWN은 여기서만 발생(자동 승격 없음).

        plans/_plan/01_PHASE1_DATA_MODEL.md §2-3-A — 모든 전이를 status_history에 남긴다
        (누가·언제·왜). WITHDRAWN/REJECTED는 reason 없이 전이 불가(추정 사유 금지).
        """
        if status not in LIFECYCLE_STATUSES:
            raise ValueError(f"미등록 lifecycle_status: {status} (허용: {sorted(LIFECYCLE_STATUSES)})")
        if status in REASON_REQUIRED_STATUSES and not reason:
            raise ValueError(f"{status} 전이는 reason이 필수다(추정 사유로 채우지 않음)")
        data = self._load_all()
        if req_id not in data:
            raise KeyError(f"존재하지 않는 req_id: {req_id}")

        record = data[req_id]
        event = StatusChangeEvent(
            from_status=record["lifecycle_status"],
            to_status=status,
            actor=actor,
            reason=reason,
            ts=datetime.now(timezone.utc).isoformat(),
        )
        record.setdefault("status_history", []).append(asdict(event))
        record["lifecycle_status"] = status
        self._save_all(data)
        return RequirementRecord(**record)

    def set_design_draft_gate(
        self, req_id: str, value: str, actor: str, reason: str | None = None,
    ) -> RequirementRecord:
        """§2-7 — 사람이 자동판정(design_draft_gate)을 override한다.

        actor="system"(자동 classifier) 또는 사람 식별자. `status_history`와 동일한
        append-only 이력 구조(StatusChangeEvent)를 그대로 재사용한다(CRZ — 신규 이력
        클래스 발명 없음). lifecycle_status의 WITHDRAWN/REJECTED와 달리 이 필드는
        비가역적이지 않아 reason을 강제(ValueError)하지 않는다(§2-7 명시).
        """
        if value not in DESIGN_GATE_VALUES:
            raise ValueError(f"미등록 design_draft_gate: {value} (허용: {sorted(DESIGN_GATE_VALUES)})")
        data = self._load_all()
        if req_id not in data:
            raise KeyError(f"존재하지 않는 req_id: {req_id}")

        record = data[req_id]
        event = StatusChangeEvent(
            from_status=record.get("design_draft_gate") or "",
            to_status=value,
            actor=actor,
            reason=reason,
            ts=datetime.now(timezone.utc).isoformat(),
        )
        record.setdefault("design_draft_gate_history", []).append(asdict(event))
        record["design_draft_gate"] = value
        record["design_draft_gate_confidence"] = 1.0
        self._save_all(data)
        return RequirementRecord(**record)

    def set_design_draft_gate_override(
        self, req_id: str, value: bool, actor: str, reason: str | None = None,
    ) -> RequirementRecord:
        """§5-2 — `design_draft_gate_override` 수기 지정. `design_draft_gate_history`를
        그대로 공유한다(신규 이력 배열 발명 없음, §5-2 명시)."""
        data = self._load_all()
        if req_id not in data:
            raise KeyError(f"존재하지 않는 req_id: {req_id}")

        record = data[req_id]
        event = {
            "field": "design_draft_gate_override",
            "from": record.get("design_draft_gate_override", False),
            "to": value,
            "actor": actor,
            "reason": reason,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        record.setdefault("design_draft_gate_history", []).append(event)
        record["design_draft_gate_override"] = value
        self._save_all(data)
        return RequirementRecord(**record)

    def request_rechunk(
        self, req_id: str, actor: str, reason: str,
        suggested_char_start: int | None = None, suggested_char_end: int | None = None,
    ) -> RequirementRecord:
        """§5-2 — 청킹 경계 오류 신고. `set_status()` 재사용 + 재청킹 큐 append만 추가(CRZ).

        기존 REJECTED 상태·status_history를 그대로 재사용하되 reason 접두사 "[RECHUNK]"로
        "청킹 재검토" 사유만 구분한다(단순 반려와 필터링 가능, §5-2 설계 그대로).
        실제 재청킹 실행(ingestion/chunking.py 재실행)은 이 함수의 책임 범위 밖 — 큐에
        남기기만 한다(자동 재청킹은 오탐 시 무한반복 위험, T98 AIP).
        """
        record = self.set_status(req_id, "REJECTED", actor=actor, reason=f"[RECHUNK] {reason}")

        self._rechunk_queue_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "req_id": req_id,
            "doc_id": record.doc_id,
            "actor": actor,
            "reason": reason,
            "suggested_char_start": suggested_char_start,
            "suggested_char_end": suggested_char_end,
            "requested_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(self._rechunk_queue_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return record

    def set_work_status(
        self, req_id: str, work_status: str, assigned_agent_command: str | None = None,
    ) -> RequirementRecord:
        """06_AGENT_DISPATCH_REPORTING.md §10-3 — 배차 결과 되먹임(write-back)용 얇은 setter.

        `set_status()`와 동일한 계약(존재하지 않는 req_id는 KeyError)이지만, lifecycle_status의
        별도 축(work_status)만 갱신한다 — status_history는 건드리지 않는다(감사로그 오염 방지,
        §10-1 "두 축 분리" 원칙 그대로).
        """
        if work_status not in WORK_STATUSES:
            raise ValueError(f"미등록 work_status: {work_status} (허용: {sorted(WORK_STATUSES)})")
        data = self._load_all()
        if req_id not in data:
            raise KeyError(f"존재하지 않는 req_id: {req_id}")

        record = data[req_id]
        record["work_status"] = work_status
        record["assigned_agent_command"] = assigned_agent_command
        record["work_status_updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_all(data)
        return RequirementRecord(**record)

    def list_all(self) -> list[RequirementRecord]:
        data = self._load_all()
        return [RequirementRecord(**record) for record in data.values()]

    def export_json(self, export_path: Path) -> None:
        """화면(agent-view)이 fetch할 수 있는 배열 형태로 내보낸다(딕셔너리 아님 — 순서 보존)."""
        records = [asdict(r) for r in self.list_all()]
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
