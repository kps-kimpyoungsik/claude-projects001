"""project_creation_service.create_project_atomic() 단위 테스트 — HTTP 레이어 없이
registry+config_store 오케스트레이션(원자성 롤백)만 검증한다.

시나리오:
1. 정상 원자적 생성 — registry 레코드 + config 파일 둘 다 남는다.
2. config 저장 실패(mock) — 방금 만든 registry 레코드가 롤백(삭제)되어 고아가 남지 않는다.
3. registry.create() 실패(mock) — config_store.save()가 아예 호출되지 않아 고아 config가
   생기지 않는다(쓰기 순서상 구조적으로 불가능함을 실측 확인).
"""

import pytest

from backend.adapters.persistence.project_config_store import ProjectConfigStore
from backend.adapters.persistence.project_registry import ProjectRegistry, ProjectValidationError
from backend.application.services.project_creation_service import (
    ProjectCreationError,
    create_project_atomic,
)


def _config_store_factory(tmp_path):
    def factory(project_id: str) -> ProjectConfigStore:
        return ProjectConfigStore(tmp_path / project_id / "project_config.json")

    return factory


def test_atomic_creation_success_persists_both_stores(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    factory = _config_store_factory(tmp_path)

    project, config = create_project_atomic(
        registry,
        factory,
        name="원자적 생성 테스트",
        start_date=None,
        end_date=None,
        config_fields={"goal": "목표 문장", "selected_areas": ["WEB"]},
        actor="tester",
    )

    assert registry.get(project.id) is not None
    reloaded = factory(project.id).load()
    assert reloaded is not None
    assert reloaded.goal == "목표 문장"
    assert reloaded.selected_areas == ["WEB"]
    assert config.goal == "목표 문장"


def test_config_save_failure_rolls_back_registry_entry(tmp_path, monkeypatch):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    factory = _config_store_factory(tmp_path)

    def _boom(self, config, created_by):
        raise RuntimeError("simulated config save failure")

    monkeypatch.setattr(ProjectConfigStore, "save", _boom)

    with pytest.raises(ProjectCreationError):
        create_project_atomic(
            registry,
            factory,
            name="롤백 대상 프로젝트",
            start_date=None,
            end_date=None,
            config_fields={"goal": "목표", "selected_areas": ["WEB"]},
            actor="tester",
        )

    # registry에 "이름만 있고 설정 없는" 고아 레코드가 남아있으면 안 된다.
    projects = registry.list_all()
    assert all(p.name != "롤백 대상 프로젝트" for p in projects)


def test_registry_create_failure_never_touches_config_store(tmp_path, monkeypatch):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    factory = _config_store_factory(tmp_path)

    save_called = []
    original_save = ProjectConfigStore.save

    def _tracking_save(self, config, created_by):
        save_called.append(True)
        return original_save(self, config, created_by)

    monkeypatch.setattr(ProjectConfigStore, "save", _tracking_save)

    with pytest.raises(ProjectValidationError):
        create_project_atomic(
            registry,
            factory,
            name="   ",  # ProjectRegistry.create()가 빈 이름을 거부
            start_date=None,
            end_date=None,
            config_fields={"goal": "목표", "selected_areas": ["WEB"]},
            actor="tester",
        )

    assert save_called == []
