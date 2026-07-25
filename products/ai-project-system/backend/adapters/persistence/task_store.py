"""[Phase 4] 태스크 JSON 영속화 — `backend/domain/task.py`에서 분리된 구체 기술 부분.

TaskStore는 "어떻게 저장하는가"(JSON 파일)만 안다 — 태스크가 무엇인지(Task 엔티티)·
충분한지(check_sufficiency)·충돌하는지(detect_area_conflicts)는 domain 계층 책임이라
여기서는 그것들을 import해서 쓰기만 한다(의존 방향: adapters → domain, 역방향 아님).
"""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from backend.adapters.persistence.task_lock_store import TaskLockStore
from backend.application.ports.task_store_port import TaskStorePort
from backend.domain.entities.task import Task
from backend.domain.requirements.conflict_detection import check_sufficiency, detect_area_conflicts
from backend.domain.requirements.task_state_machine import (
    BLOCKED_CIRCUIT_BREAKER_THRESHOLD,
    build_status_change_event,
    check_circuit_breaker,
    count_blocked_transitions,
    validate_transition,
)

# IN_PROGRESS 전이 시 배타 점유가 걸리는 상태 집합(그 외에서 IN_PROGRESS로 들어올 때만 락 획득).
_LOCKED_STATUS = "IN_PROGRESS"


class TaskStore(TaskStorePort):
    """`TaskStorePort`의 JSON 파일 구현체 (경량 — DB 의존 없음, 이 프로젝트의 다른 JSON
    스토어들과 동일 패턴).

    PostgreSQL 등으로 교체 시 이 클래스처럼 `TaskStorePort`를 구현하는 새 어댑터만
    작성하면 되고, 호출부(`tasks_api.py`)만 바꾸면 된다.

    [Phase 4.3] `lock_store`를 지정하지 않으면 같은 디렉터리의 `task_locks.json`을 기본값으로
    자동 생성한다(호출자가 매번 명시하지 않아도 병렬 작업 통제가 기본 적용되도록, CRZ —
    RequirementStore가 DocumentStore 경로를 자체 규약으로 정하는 것과 동일 원칙).
    """

    def __init__(self, store_path: Path, lock_store: TaskLockStore | None = None):
        self._path = store_path
        self._lock_store = lock_store or TaskLockStore(store_path.parent / "task_locks.json")

    def _load_all(self) -> dict:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _save_all(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def create_or_update(self, task: Task, graph: dict | None = None) -> Task:
        """태스크를 생성/갱신하고, 충분성 체크 결과를 즉시 반영한다.

        내용이 부족하면 status를 강제로 "DRAFT"에 묶어두고(READY로 승격 금지) needs_escalation=True —
        호출자는 이 플래그를 보고 `/aegis-oneshot-plan`으로 설계를 구체화해야 한다.

        graph를 넘기면 요구사항 그래프 실재 검증(verify_task_requirement_links)까지 함께 수행한다.
        """
        sufficient, reasons = check_sufficiency(task, graph=graph)
        task.needs_escalation = not sufficient
        task.escalation_reasons = reasons
        if not sufficient and task.status not in ("DRAFT",):
            task.status = "DRAFT"  # 불충분한 태스크는 실행 가능 상태로 승격 불가
        task.updated_at = datetime.now(timezone.utc).isoformat()

        data = self._load_all()
        existing = data.get(task.task_id)
        task.revision = (existing["revision"] + 1) if existing else 1
        data[task.task_id] = asdict(task)
        self._save_all(data)
        return task

    def get(self, task_id: str) -> Task | None:
        data = self._load_all()
        record = data.get(task_id)
        return Task(**record) if record else None

    def list_all(self) -> list[Task]:
        data = self._load_all()
        return [Task(**record) for record in data.values()]

    def check_all_conflicts(self) -> dict:
        return detect_area_conflicts(self.list_all())

    def generate_task_id(self, domain_code: str) -> str:
        """[Phase 4.2 보완] `REQ-{코드}-{3자리 일련번호}`(id_format.build_req_id) 채번
        방식과 동일 원칙으로 `TASK-{domain_code}-{3자리 일련번호}`를 채번한다(CRZ — 별도
        포맷 발명 없음). 도메인코드별로 독립 증가(다른 도메인끼리 번호가 섞이지 않음)."""
        data = self._load_all()
        prefix = f"TASK-{domain_code}-"
        existing_seqs = [
            int(task_id[len(prefix):])
            for task_id in data
            if task_id.startswith(prefix) and task_id[len(prefix):].isdigit()
        ]
        next_seq = max(existing_seqs, default=0) + 1
        return f"{prefix}{next_seq:03d}"

    def set_status(
        self,
        task_id: str,
        status: str,
        actor: str,
        reason: str | None = None,
        override_escalation: bool = False,
    ) -> Task:
        """[Phase 4.2] 검증된 상태 전이 — 배차된 agent(또는 이를 대행하는 세션)가 진행상황을
        보고하는 유일한 쓰기 경로. `task_state_machine.validate_transition()`이 전이 그래프를
        확인하고, 통과하면 `status_history`에 append한다(RequirementStore.set_status()와
        동일 감사로그 패턴, CRZ).

        [Phase 5.3] `needs_escalation=True`(서킷 브레이커 트립)인 Task는
        `override_escalation=True`(사람이 검토했음을 명시)를 전달해야만 전이가 허용된다.
        """
        data = self._load_all()
        if task_id not in data:
            raise KeyError(f"존재하지 않는 task_id: {task_id}")

        record = data[task_id]
        from_status = record["status"]
        check_circuit_breaker(record.get("needs_escalation", False), override_escalation, status)
        validate_transition(from_status, status, reason)

        # [Phase 4.3] IN_PROGRESS 진입 = impact_scope 배타 점유 시도(다른 Task가 겹치는
        # 경로를 이미 점유 중이면 여기서 거부되어 상태 변경 자체가 저장되지 않는다 — 부분
        # 반영 방지). IN_PROGRESS 이탈 = 점유 해제(READY/BLOCKED/DONE 어디로 가든 동일).
        entering_in_progress = status == _LOCKED_STATUS and from_status != _LOCKED_STATUS
        leaving_in_progress = from_status == _LOCKED_STATUS and status != _LOCKED_STATUS
        if entering_in_progress:
            self._lock_store.acquire(task_id, record.get("impact_scope", []))

        event = build_status_change_event(from_status, status, actor, reason)
        record.setdefault("status_history", []).append(event)
        record["status"] = status
        record["updated_at"] = datetime.now(timezone.utc).isoformat()

        # [Phase 5.3] BLOCKED 도달 횟수가 임계치에 이르면 서킷 브레이커 트립 — needs_escalation을
        # 세워 사람 검토 없이는 더 진행 못 하게 한다. override_escalation=True로 사람이 검토를
        # 확인하며 BLOCKED에서 벗어나면 브레이커를 리셋한다(재트립 가능 — 1회성 해제 아님).
        if status == "BLOCKED" and count_blocked_transitions(record["status_history"]) >= BLOCKED_CIRCUIT_BREAKER_THRESHOLD:
            record["needs_escalation"] = True
            record.setdefault("escalation_reasons", []).append(
                f"서킷 브레이커: BLOCKED {BLOCKED_CIRCUIT_BREAKER_THRESHOLD}회 이상 도달 — 사람 검토 필요"
            )
        elif override_escalation and record.get("needs_escalation") and status != "BLOCKED":
            record["needs_escalation"] = False
            record["escalation_reasons"] = []

        self._save_all(data)

        if leaving_in_progress:
            self._lock_store.release(task_id)
        return Task(**record)
