"""[Phase 3 Ext] agent 역할 사용 이력 append-only 로그 (설계:
plans/_plan/06_AGENT_DISPATCH_REPORTING.md §9-2).

"이 프로젝트가 실제로 어떤 AEGIS agent 역할을 어떤 영역에 쓰고 있는지"의 ground-truth
기록 — 자가보고가 아니라 실제 배차(resolve_agent_for_domain) 이벤트 로그다. 세션 종료
또는 "자산화 승인" 시점에 기존 `/assetize` 경로가 이 로그를 요약해 AEGIS
`base/04_memory/knowhow/_reports/`로 흡수한다(§9-2 — 신규 동기화 데몬 아님).

기존 TaskStore/RequirementStore와 동일한 "JSON 파일 기반 경량 스토어" 패턴을 그대로
따른다 — 다만 이 로그는 append-only(레코드를 덮어쓰지 않고 리스트에 계속 추가)라는 점만
다르다(CRZ — 새 저장 패턴 발명 아님, 기존 JSON 파일 패턴의 자연스러운 변형).
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class AgentRoleUsageEntry:
    domain_code: str
    agent_command: str | None
    resolution_source: str  # "search_all" | "fallback_default" | "cache"
    resolved_at: str


class AgentRoleUsageLog:
    """append-only JSON 로그 어댑터 — `{"entries": [...]}` 형태로 저장한다."""

    def __init__(self, store_path: Path):
        self._path = store_path

    def _load(self) -> dict:
        if not self._path.exists():
            return {"entries": []}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def record(
        self, domain_code: str, agent_command: str | None, resolution_source: str, resolved_at: str
    ) -> AgentRoleUsageEntry:
        entry = AgentRoleUsageEntry(
            domain_code=domain_code,
            agent_command=agent_command,
            resolution_source=resolution_source,
            resolved_at=resolved_at,
        )
        data = self._load()
        data.setdefault("entries", []).append(asdict(entry))
        self._save(data)
        return entry

    def list_all(self) -> list[AgentRoleUsageEntry]:
        data = self._load()
        return [AgentRoleUsageEntry(**e) for e in data.get("entries", [])]
