"""project_consistency_check.find_orphans() 단위 테스트 — 기존 데이터에서 고아(project↔config
불일치) 실측 탐지만 검증한다. **탐지만** — 자동 삭제·자동 수정 로직은 이 모듈에 아예 없다(설계
자체가 그렇게 되어 있음을 이 테스트가 간접 증명: 반환값은 읽기전용 dict뿐).

모든 테스트가 `data_root=tmp_path`를 명시한다 — 생략하면 `project_scope.DATA_ROOT`(cwd 기준
실제 `data/`)를 스캔해 실제 프로젝트 데이터와 섞여 회귀가 난다(최초 구현 실측 발견 버그,
`find_orphans()`의 `data_root` 파라미터가 그 수정)."""

from backend.adapters.persistence.project_config_store import ProjectConfig, ProjectConfigStore
from backend.adapters.persistence.project_registry import ProjectRegistry
from backend.application.services.project_consistency_check import find_orphans


def _config_store_factory(tmp_path):
    def factory(project_id: str) -> ProjectConfigStore:
        return ProjectConfigStore(tmp_path / project_id / "project_config.json")

    return factory


def test_find_orphans_reports_project_without_config(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    created = registry.create("설정 없는 프로젝트")
    factory = _config_store_factory(tmp_path)

    result = find_orphans(registry, factory, data_root=tmp_path)

    # DEFAULT_PROJECT_ID는 `list_all()`이 항상 가상으로 포함하고 이 tmp_path에는 default
    # config도 없으므로 함께 잡힌다(정상 — 실제 신규 설치 상태와 동일) — 방금 만든
    # project_id가 포함되는지로 확인한다(개수 고정값 비교는 하지 않음, CRZ 취약점 회피).
    assert created.id in result["projects_without_config"]
    assert result["configs_without_project"] == []


def test_find_orphans_clean_when_config_exists(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    project = registry.create("설정 있는 프로젝트")
    factory = _config_store_factory(tmp_path)
    store = factory(project.id)
    store.save(
        ProjectConfig(project_name=project.name, goal="목표", selected_areas=["WEB"]),
        created_by="tester",
    )

    result = find_orphans(registry, factory, data_root=tmp_path)

    # 이 project.id는 config가 있으니 빠져야 한다 — DEFAULT_PROJECT_ID는 이 tmp_path에
    # config가 없어 별개로 잡힐 수 있으므로(fixture 특성) 그 자체는 검증 대상이 아니다.
    assert project.id not in result["projects_without_config"]
    assert result["configs_without_project"] == []


def test_find_orphans_reports_config_without_project(tmp_path):
    """수동으로 만든 고아 케이스: `{data_root}/projects/{id}/project_config.json`은 있는데
    그 id가 registry에는 없는 상황(예: registry 파일이 수동 편집·손상된 경우)을 재현한다."""
    registry = ProjectRegistry(tmp_path / "projects_registry.json")  # 비어있음(고아 id 없음)

    orphan_dir = tmp_path / "projects" / "proj-ghost"
    orphan_dir.mkdir(parents=True)
    ghost_store = ProjectConfigStore(orphan_dir / "project_config.json")
    ghost_store.save(
        ProjectConfig(project_name="유령 프로젝트", goal="목표", selected_areas=["WEB"]),
        created_by="tester",
    )

    def factory(project_id: str) -> ProjectConfigStore:
        return ProjectConfigStore(tmp_path / "projects" / project_id / "project_config.json")

    result = find_orphans(registry, factory, data_root=tmp_path)

    assert "proj-ghost" in result["configs_without_project"]
