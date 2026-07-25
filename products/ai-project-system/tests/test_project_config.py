"""프로젝트 등록(0차) 설정 검증·영속화 회귀 테스트."""

import pytest

from backend.adapters.persistence.project_config_store import (
    ProjectConfig,
    ProjectConfigStore,
    ProjectConfigValidationError,
    validate_project_config,
)


def test_empty_config_fails_validation():
    reasons = validate_project_config(ProjectConfig(project_name="", goal="", selected_areas=[]))
    assert len(reasons) == 3


def test_valid_config_passes_and_persists(tmp_path):
    cfg = ProjectConfig(
        project_name="결제시스템 요구사항 관리",
        goal="요구사항 문서를 받아 영역별 태스크로 관리한다",
        selected_areas=["WEB", "SEC"],
        access_policy="SHARED",
    )
    store = ProjectConfigStore(tmp_path / "project_config.json")
    saved = store.save(cfg, created_by="pm@example.com")
    assert saved.created_by == "pm@example.com"
    assert saved.created_at

    loaded = store.load()
    assert loaded.project_name == cfg.project_name
    assert loaded.selected_areas == ["WEB", "SEC"]


def test_unknown_area_code_rejected(tmp_path):
    cfg = ProjectConfig(project_name="x", goal="y", selected_areas=["NOT_A_REAL_AREA"])
    store = ProjectConfigStore(tmp_path / "project_config.json")
    with pytest.raises(ProjectConfigValidationError):
        store.save(cfg, created_by="pm")


def test_load_returns_none_when_no_config_saved(tmp_path):
    store = ProjectConfigStore(tmp_path / "project_config.json")
    assert store.load() is None
