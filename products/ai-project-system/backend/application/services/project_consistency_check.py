"""[2026-07-27 신설] 기존 데이터의 고아(orphan) 탐지 — **탐지·보고만 한다, 자동 삭제·자동
수정 절대 금지**(기존 데이터를 건드리는 것은 데이터 파괴적 결정이라 이번 범위 밖 — 사용자가
직접 판단해야 함).

`create_project_atomic()`(project_creation_service.py)은 이번 시점 이후의 *신규* 생성만
안전화한다 — 이 함수는 그 이전에 이미 두 저장소가 어긋나 있을 수 있는 *기존* 데이터를
찾아낸다. 두 방향 모두 확인한다:

1. `projects_without_config` — registry에는 있는데 `ProjectConfig`가 없는 프로젝트.
2. `configs_without_project` — `data/projects/{id}/project_config.json` 파일은 있는데
   registry에 그 `{id}`가 없는 경우(예: registry 파일이 수동으로 편집되거나 손상된 경우).
"""

from pathlib import Path
from typing import Callable

from backend.adapters.persistence import project_scope
from backend.adapters.persistence.project_config_store import ProjectConfigStore
from backend.adapters.persistence.project_registry import DEFAULT_PROJECT_ID, ProjectRegistry


def find_orphans(
    registry: ProjectRegistry,
    config_store_factory: Callable[[str], ProjectConfigStore],
    data_root: Path | None = None,
) -> dict:
    """`data_root`를 명시적 인자로 받는다(기본값 `project_scope.DATA_ROOT`) — 반대 방향
    탐지(아래)는 `config_store_factory`가 실제로 어느 경로에 파일을 쓰는지와 무관하게
    모듈 레벨 상수만 보면 테스트(tmp_path 격리)와 실제 실행(cwd 기준 `data/`)이 어긋난다
    (실측 발견 — 최초 구현이 `project_scope.DATA_ROOT`를 하드코딩해 테스트에서 실제
    `data/projects/*`를 스캔하는 회귀가 있었다). 호출부(`projects_api.py`)는 인자를
    생략해 기존 `project_scope.DATA_ROOT` 그대로 사용한다."""
    if data_root is None:
        data_root = project_scope.DATA_ROOT

    projects = registry.list_all()
    project_ids = {p.id for p in projects}

    projects_without_config = [
        p.id for p in projects if config_store_factory(p.id).load() is None
    ]

    # 반대 방향 — `project_config_store.py`는 project_id별 개별 파일이라 "전체 config
    # 목록" API가 없다. `project_scope.resolve_project_data_dir()`가 만드는 실제 디렉터리
    # 구조(`{data_root}/projects/{id}/project_config.json`)를 직접 스캔해야 발견 가능하다.
    configs_without_project = []
    projects_dir = data_root / "projects"
    if projects_dir.exists():
        for child in sorted(projects_dir.iterdir()):
            if child.is_dir() and (child / "project_config.json").exists():
                if child.name not in project_ids:
                    configs_without_project.append(child.name)

    # DEFAULT_PROJECT_ID는 평면 경로(`{data_root}/project_config.json`)를 쓰고
    # `list_all()`이 항상 가상으로 포함하므로 이 분기는 정상 상태에서는 도달하지 않는다 —
    # registry 파일이 손상돼 DEFAULT조차 빠지는 극단적 경우를 대비한 방어적 확인.
    default_config_path = data_root / "project_config.json"
    if default_config_path.exists() and DEFAULT_PROJECT_ID not in project_ids:
        configs_without_project.append(DEFAULT_PROJECT_ID)

    return {
        "projects_without_config": projects_without_config,
        "configs_without_project": configs_without_project,
    }
