"""[Phase 3 §2] ProjectDomainSnapshot 영속화 — 기존 JSON 스토어 패턴 재사용
(`TaskStore`/`ProjectConfigStore`와 동일 스타일 — 신규 저장 방식 발명 없음, CRZ).

**이력(diff) 관리 청크(2026-07-20) 범위**: `load_previous()`를 추가해 `save()`로 덮어쓰기
전에 직전 스냅샷을 조회할 수 있게 한다. 이 스토어는 프로젝트당 파일 하나만 다루는 스코프이므로
(`ProjectConfigStore`와 동일 원칙) "직전 스냅샷"은 곧 `save()` 호출 직전 시점의 `load()`
결과와 같다 — `load_previous()`는 그 의도를 명확히 드러내는 별칭 메서드다(신규 저장 로직
없음, 기존 `load()` 재사용). 실제 diff 비교(무엇이 추가/삭제/변경됐는지)는
`project_domain_snapshot_service.diff_snapshots()`가 맡는다 — 스토어는 여전히 저장/조회만
한다(관심사 분리).
"""

import json
from pathlib import Path


class ProjectDomainSnapshotStore:
    """단일 프로젝트의 최신 ProjectDomainSnapshot을 JSON 파일로 저장/조회한다.

    프로젝트당 하나의 최신 스냅샷만 다룬다(`ProjectConfigStore`와 동일 스코프 원칙 —
    이 인스턴스는 "프로젝트 하나"를 관리하는 도구, 00_PROJECT_CONSTITUTION.md 스코프).
    """

    def __init__(self, store_path: Path):
        self._path = Path(store_path)

    def save(self, snapshot: dict) -> dict:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        return snapshot

    def load(self) -> dict | None:
        if not self._path.exists():
            return None
        return json.loads(self._path.read_text(encoding="utf-8"))

    def load_previous(self) -> dict | None:
        """`save()`로 최신 스냅샷을 덮어쓰기 전, 직전에 저장된 스냅샷을 조회한다.

        이 스토어는 프로젝트당 최신 스냅샷 1개만 보관하므로 "직전 스냅샷"은 곧 지금
        저장돼 있는 파일(`load()`)이다 — 별도 이력 파일을 새로 만들지 않는다(CRZ, 과잉
        설계 회피). 최초 실행 등으로 저장된 적이 없으면 None을 반환한다.
        """
        return self.load()
