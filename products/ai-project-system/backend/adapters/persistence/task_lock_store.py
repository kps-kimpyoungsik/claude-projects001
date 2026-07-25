"""[Phase 4.3] 파일 기반 분산 락 — Task별 impact_scope 배타 점유.

`backend/domain/requirements/conflict_detection.detect_area_conflicts()`는 배차 "계획"
단계에서 impact_scope 겹침을 감지만 할 뿐(순수 함수, 상태 없음) 실행을 막지는 않는다 —
계획을 무시하고 겹치는 두 Task를 동시에 IN_PROGRESS로 전이시켜도 코드로는 막을 방법이
없었다(실측 확인). 이 모듈이 그 갭을 메운다: Task가 실제로 IN_PROGRESS로 전이할 때 그
impact_scope 경로들을 배타 점유하고, 다른 Task가 겹치는 경로로 동시에 IN_PROGRESS
전이를 시도하면 거부한다.

AEGIS 자체의 `claim_llm_task.py`(파일 기반 claim registry, 전역 다중 LLM 세션 간 조율)와
동일 원칙을 이 프로젝트 로컬 스코프(Task 단위)로 재구현한다 — 그 전역 도구를 프로젝트
코드가 직접 import하지 않는다(프로젝트 경계 유지, T64 KAAG 정신과 정합: 상품 프로젝트는
AEGIS 관리자 영역 도구에 직접 의존하지 않는다).
"""

import json
from pathlib import Path


class TaskLockConflictError(ValueError):
    pass


class TaskLockStore:
    """JSON 파일 기반 배타 락 저장소 (경량 — 이 프로젝트의 다른 JSON 스토어들과 동일 패턴)."""

    def __init__(self, store_path: Path):
        self._path = store_path

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def acquire(self, task_id: str, impact_scope: list[str]) -> None:
        """impact_scope 전체를 점유 시도 — 하나라도 다른 task_id가 이미 점유 중이면 전부
        거부한다(부분 점유 금지 — 절반만 잠그고 실패하면 불일치 상태가 남는다).
        같은 task_id의 재점유(이미 갖고 있는 경로)는 충돌로 보지 않는다(멱등)."""
        data = self._load()
        conflicts = {
            path: data[path]["task_id"]
            for path in impact_scope
            if path in data and data[path]["task_id"] != task_id
        }
        if conflicts:
            raise TaskLockConflictError(
                f"impact_scope 충돌 — 다른 Task가 이미 점유 중(병렬 진행 불가): {conflicts}"
            )
        for path in impact_scope:
            data[path] = {"task_id": task_id}
        self._save(data)

    def release(self, task_id: str) -> None:
        """해당 task_id가 점유한 락을 전부 해제한다. 애초에 점유한 게 없어도 안전(멱등)."""
        data = self._load()
        remaining = {path: v for path, v in data.items() if v["task_id"] != task_id}
        if remaining != data:
            self._save(remaining)

    def held_by(self, task_id: str) -> list[str]:
        data = self._load()
        return sorted(path for path, v in data.items() if v["task_id"] == task_id)

    def all_locks(self) -> dict[str, str]:
        """path -> task_id 전체 조회(진단·표면화용)."""
        return {path: v["task_id"] for path, v in self._load().items()}
