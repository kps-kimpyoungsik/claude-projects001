"""ProjectRegistry(project_registry.py) 단위 테스트 — "여러 프로젝트 관리" 고도화의 핵심.

무마이그레이션 원칙(레지스트리가 비어 있어도 DEFAULT_PROJECT_ID가 항상 보임)과
신규 프로젝트 생성·채번을 검증한다.
"""

from backend.adapters.persistence.project_registry import (
    DEFAULT_PROJECT_ID,
    ProjectRegistry,
    ProjectValidationError,
)


def test_list_all_always_includes_default_when_registry_empty(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    projects = registry.list_all()
    assert any(p.id == DEFAULT_PROJECT_ID for p in projects)
    assert len(projects) == 1


def test_create_project_persists_and_reloads(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    created = registry.create("테스트 프로젝트")
    assert created.id != DEFAULT_PROJECT_ID
    assert created.status == "IMPLEMENTING"

    reloaded = ProjectRegistry(tmp_path / "projects_registry.json")
    projects = reloaded.list_all()
    ids = [p.id for p in projects]
    assert DEFAULT_PROJECT_ID in ids
    assert created.id in ids


def test_create_project_empty_name_raises():
    registry = ProjectRegistry(None)
    import pytest
    with pytest.raises(ProjectValidationError):
        registry.create("   ")


def test_create_project_assigns_unique_sequential_ids(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    p1 = registry.create("A")
    p2 = registry.create("B")
    assert p1.id != p2.id


def test_get_returns_none_for_unknown_id(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    assert registry.get("proj-999") is None
    assert registry.get(DEFAULT_PROJECT_ID) is not None
