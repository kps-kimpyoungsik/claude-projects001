"""[Phase 3.2] Context Manager — 영속적 작업 상태 관리.

TASK_STATE.md/json 관리 + Context Pruning(가지치기). error_log 조회는 실제
AEGIS error_kb 디렉터리를 grep하는 방식을 그대로 재사용한다(신규 검색엔진 발명 금지 —
governance/workflows/RECALL_UNIVERSAL_SEARCH_GUIDE.md 원칙과 동일).
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class TaskState:
    task_id: str
    status: str  # WAITING, IMPLEMENTING, TESTING, VERIFIED
    decisions: list[str] = field(default_factory=list)  # Decision Record만 보관(로그 원문 아님)


class TaskStateStore:
    """단일 JSON 파일 기반 영속 상태 저장소 (경량 — DB 의존 없음)."""

    def __init__(self, state_path: Path):
        self._path = state_path

    def load(self, task_id: str) -> TaskState | None:
        if not self._path.exists():
            return None
        data = json.loads(self._path.read_text(encoding="utf-8"))
        record = data.get(task_id)
        return TaskState(**record) if record else None

    def save(self, state: TaskState) -> None:
        data = {}
        if self._path.exists():
            data = json.loads(self._path.read_text(encoding="utf-8"))
        data[state.task_id] = asdict(state)
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def prune_context(decisions: list[str], keep_last: int = 10) -> list[str]:
    """Context Pruning — 핵심 합의사항(Decision Record)만 최근 N개 유지.

    "불필요한 로그 삭제"는 이 함수가 받는 입력을 이미 Decision Record로 한정함으로써
    구조적으로 보장한다(원본 대화 로그 자체를 여기서 다루지 않음 — 원본은 별도 보존,
    삭제 없음 원칙 T90 DELP와 충돌하지 않음).
    """
    return decisions[-keep_last:] if len(decisions) > keep_last else decisions
