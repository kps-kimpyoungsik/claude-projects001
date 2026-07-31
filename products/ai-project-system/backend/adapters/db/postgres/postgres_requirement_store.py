"""`RequirementStorePort`의 PostgreSQL 구현체 (2026-07-24 신설).

⚠ 검증 미확정 — README.md 참조. 비즈니스 로직(REQ ID 채번 규칙·PII 스캔·lifecycle_status
검증·감사이력 구조)은 `requirement_store.py`(JSON 어댑터)가 정의한 동일 dataclass·상수·
domain 함수를 그대로 재사용한다 — 로직 재구현이 아니라 저장 메커니즘만 교체(CRZ).
`RequirementStore`의 Port 외 공개 메서드(`set_design_draft_gate` 등)도 동일하게 제공해
드롭인 교체가 가능하도록 했다.
"""

from dataclasses import asdict
from datetime import datetime, timezone

from backend.adapters.db.postgres.connection import get_connection
from backend.adapters.persistence.requirement_store import (
    LIFECYCLE_STATUSES,
    REASON_REQUIRED_STATUSES,
    WORK_STATUSES,
    RequirementRecord,
    StatusChangeEvent,
)
from backend.application.ports.requirement_store_port import RequirementStorePort
from backend.domain.requirements.classifier import ClassificationResult
from backend.domain.requirements.codes import DESIGN_GATE_VALUES
from backend.domain.requirements.id_format import build_req_id
from backend.domain.requirements.pii_detector import scan_for_pii


def _json(data: dict):
    from psycopg2.extras import Json
    return Json(data)


class PostgresRequirementStore(RequirementStorePort):
    def __init__(self, conn=None):
        self._conn = conn

    def _connection(self):
        return self._conn or get_connection()

    def _next_seq(self, cur, doc_type_code: str, area_code: str) -> int:
        prefix = f"REQ-{doc_type_code}-{area_code}-"
        cur.execute("SELECT req_id FROM requirements WHERE req_id LIKE %s", (f"{prefix}%",))
        existing_seqs = [int(r["req_id"][len(prefix):]) for r in cur.fetchall()]
        return (max(existing_seqs) + 1) if existing_seqs else 1

    def add_from_classification(
        self, classification: ClassificationResult, description: str, source_ref: str,
        doc_id: str = "", heading_path: list | None = None,
        char_start: int | None = None, char_end: int | None = None,
        source_is_image: bool = False,
        related_chunks: list[dict] | None = None,
        extra_doc_types: set[str] | None = None,
    ) -> RequirementRecord | None:
        if not classification.doc_type_code or not classification.area_code:
            return None

        conn = self._connection()
        with conn.cursor() as cur:
            seq = self._next_seq(cur, classification.doc_type_code, classification.area_code)
            req_id = build_req_id(
                classification.doc_type_code, classification.area_code, seq,
                extra_doc_types=extra_doc_types,
            )
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
            data = asdict(record)
            cur.execute(
                "INSERT INTO requirements (req_id, doc_type_code, area_code, lifecycle_status, data) "
                "VALUES (%s, %s, %s, %s, %s)",
                (req_id, record.doc_type_code, record.area_code, record.lifecycle_status, _json(data)),
            )
        conn.commit()
        return record

    def _load_record(self, cur, req_id: str) -> dict:
        cur.execute("SELECT data FROM requirements WHERE req_id = %s", (req_id,))
        row = cur.fetchone()
        if not row:
            raise KeyError(f"존재하지 않는 req_id: {req_id}")
        return row["data"]

    def _save_record(self, cur, req_id: str, record: dict) -> None:
        cur.execute(
            "UPDATE requirements SET lifecycle_status = %s, data = %s WHERE req_id = %s",
            (record["lifecycle_status"], _json(record), req_id),
        )

    def set_status(self, req_id: str, status: str, actor: str, reason: str | None = None) -> RequirementRecord:
        if status not in LIFECYCLE_STATUSES:
            raise ValueError(f"미등록 lifecycle_status: {status} (허용: {sorted(LIFECYCLE_STATUSES)})")
        if status in REASON_REQUIRED_STATUSES and not reason:
            raise ValueError(f"{status} 전이는 reason이 필수다(추정 사유로 채우지 않음)")

        conn = self._connection()
        with conn.cursor() as cur:
            record = self._load_record(cur, req_id)
            event = StatusChangeEvent(
                from_status=record["lifecycle_status"], to_status=status, actor=actor,
                reason=reason, ts=datetime.now(timezone.utc).isoformat(),
            )
            record.setdefault("status_history", []).append(asdict(event))
            record["lifecycle_status"] = status
            self._save_record(cur, req_id, record)
        conn.commit()
        return RequirementRecord(**record)

    def set_design_draft_gate(
        self, req_id: str, value: str, actor: str, reason: str | None = None,
    ) -> RequirementRecord:
        if value not in DESIGN_GATE_VALUES:
            raise ValueError(f"미등록 design_draft_gate: {value} (허용: {sorted(DESIGN_GATE_VALUES)})")

        conn = self._connection()
        with conn.cursor() as cur:
            record = self._load_record(cur, req_id)
            event = StatusChangeEvent(
                from_status=record.get("design_draft_gate") or "", to_status=value,
                actor=actor, reason=reason, ts=datetime.now(timezone.utc).isoformat(),
            )
            record.setdefault("design_draft_gate_history", []).append(asdict(event))
            record["design_draft_gate"] = value
            record["design_draft_gate_confidence"] = 1.0
            self._save_record(cur, req_id, record)
        conn.commit()
        return RequirementRecord(**record)

    def set_design_draft_gate_override(
        self, req_id: str, value: bool, actor: str, reason: str | None = None,
    ) -> RequirementRecord:
        conn = self._connection()
        with conn.cursor() as cur:
            record = self._load_record(cur, req_id)
            event = {
                "field": "design_draft_gate_override",
                "from": record.get("design_draft_gate_override", False),
                "to": value, "actor": actor, "reason": reason,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            record.setdefault("design_draft_gate_history", []).append(event)
            record["design_draft_gate_override"] = value
            self._save_record(cur, req_id, record)
        conn.commit()
        return RequirementRecord(**record)

    def request_rechunk(
        self, req_id: str, actor: str, reason: str,
        suggested_char_start: int | None = None, suggested_char_end: int | None = None,
    ) -> RequirementRecord:
        record = self.set_status(req_id, "REJECTED", actor=actor, reason=f"[RECHUNK] {reason}")

        conn = self._connection()
        with conn.cursor() as cur:
            entry = {
                "req_id": req_id, "doc_id": record.doc_id, "actor": actor, "reason": reason,
                "suggested_char_start": suggested_char_start,
                "suggested_char_end": suggested_char_end,
                "requested_at": datetime.now(timezone.utc).isoformat(),
            }
            cur.execute("INSERT INTO rechunk_queue (entry) VALUES (%s)", (_json(entry),))
        conn.commit()
        return record

    def set_work_status(
        self, req_id: str, work_status: str, assigned_agent_command: str | None = None,
    ) -> RequirementRecord:
        if work_status not in WORK_STATUSES:
            raise ValueError(f"미등록 work_status: {work_status} (허용: {sorted(WORK_STATUSES)})")

        conn = self._connection()
        with conn.cursor() as cur:
            record = self._load_record(cur, req_id)
            record["work_status"] = work_status
            record["assigned_agent_command"] = assigned_agent_command
            record["work_status_updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save_record(cur, req_id, record)
        conn.commit()
        return RequirementRecord(**record)

    def list_all(self) -> list[RequirementRecord]:
        conn = self._connection()
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM requirements ORDER BY req_id")
            rows = cur.fetchall()
        return [RequirementRecord(**r["data"]) for r in rows]
